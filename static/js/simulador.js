/*
 * Simulador de estratégia nutricional — d3.js (Fase 2)
 *
 * Dois modos:
 *   1. "ingestao": arrasta os pontos da curva de ingestão (kcal/dia por semana)
 *      → projeção de peso ao vivo (regra 7700 kcal/kg).
 *   2. "alvo": arrasta o peso final → ingestão constante necessária.
 *
 * Paleta azul monocromática (acessível a daltônicos deuteranopia/protanopia).
 */
(function () {
    "use strict";

    const KCAL_POR_KG = 7700;
    const cfg = window.SIMULADOR;
    const tooltip = d3.select("#sim-tooltip");

    // ── Estado ────────────────────────────────────────────────────────
    let state = null;      // dados do plano (GET /simulador/dados)
    let pontos = [];       // [{semana, kcal}] — curva de ingestão
    let modo = "ingestao"; // ingestao | alvo
    let pesoAlvoAtual = null;

    // ── Geometria ─────────────────────────────────────────────────────
    const margin = { top: 30, right: 85, bottom: 45, left: 70 };
    const W = 800, H = 440;
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;

    let svg = null, camadas = null;
    let x = null, yKcal = null, yPeso = null;

    // ══════════════════════════════════════════════════════════════════
    // Cálculos
    // ══════════════════════════════════════════════════════════════════

    function semanasTotais() {
        return Math.max(1, Math.ceil(state.prazo_dias / 7));
    }

    function kcalNoDia(dia) {
        // Interpolação linear entre os pontos semanais
        const sem = dia / 7;
        if (sem <= pontos[0].semana) return pontos[0].kcal;
        for (let i = 0; i < pontos.length - 1; i++) {
            const a = pontos[i], b = pontos[i + 1];
            if (sem >= a.semana && sem <= b.semana) {
                const t = (b.semana - a.semana) === 0 ? 0 : (sem - a.semana) / (b.semana - a.semana);
                return a.kcal + t * (b.kcal - a.kcal);
            }
        }
        return pontos[pontos.length - 1].kcal;
    }

    function mediaIngestao() {
        let soma = 0;
        for (let d = 1; d <= state.prazo_dias; d++) soma += kcalNoDia(d);
        return soma / state.prazo_dias;
    }

    function projetarPeso() {
        // [{semana, peso}] — a cada 7 dias e no dia final
        const serie = [{ semana: 0, peso: +state.peso_atual_kg.toFixed(2) }];
        let peso = state.peso_atual_kg;
        for (let d = 1; d <= state.prazo_dias; d++) {
            peso += (kcalNoDia(d) - state.get_kcal) / KCAL_POR_KG;
            if (d % 7 === 0 || d === state.prazo_dias) {
                serie.push({ semana: +(d / 7).toFixed(2), peso: +peso.toFixed(2) });
            }
        }
        return serie;
    }

    function ingestaoConstanteParaPeso(pesoAlvo) {
        return state.get_kcal + (pesoAlvo - state.peso_atual_kg) * KCAL_POR_KG / state.prazo_dias;
    }

    function faixaSegura() {
        // [min, max] kcal/dia da faixa de balanço seguro (déficit/superávit moderado)
        const g = state.get_kcal;
        if (state.objetivo === "perder") return [g - 1000, g - 500];
        if (state.objetivo === "ganhar") return [g + 300, g + 1000];
        return [g - 100, g + 100];
    }

    function clampKcal(v) {
        return Math.min(state.get_kcal + 1500, Math.max(Math.max(800, state.get_kcal - 1500), Math.round(v)));
    }

    function clampPeso(v) {
        return Math.min(state.peso_atual_kg + 25, Math.max(state.peso_atual_kg - 25, Math.round(v * 10) / 10));
    }

    // ══════════════════════════════════════════════════════════════════
    // Render
    // ══════════════════════════════════════════════════════════════════

    function atualizarMetricas() {
        const serie = projetarPeso();
        const fim = serie[serie.length - 1].peso;
        const media = mediaIngestao();
        const balanco = media - state.get_kcal;
        const taxa = (fim - state.peso_atual_kg) / (state.prazo_dias / 7);

        d3.select("#m-get").text(Math.round(state.get_kcal));
        d3.select("#m-meta").text(Math.round(media));
        d3.select("#m-deficit").text((balanco >= 0 ? "+" : "") + Math.round(balanco));
        d3.select("#m-peso-atual").text(state.peso_atual_kg.toFixed(1));
        d3.select("#m-peso-fim").text(fim.toFixed(1));
        d3.select("#m-taxa").text((taxa >= 0 ? "+" : "") + taxa.toFixed(2));

        // Aviso de estratégia agressiva (âmbar — seguro p/ daltônicos)
        const card = d3.select("#m-deficit").node().closest(".sim-card");
        const agressivo = (state.objetivo === "perder" && balanco < -1000) ||
                          (state.objetivo === "ganhar" && balanco > 1000) ||
                          media < 800;
        card.classList.toggle("aviso", agressivo);

        d3.select("#sim-prazo-info").text(
            `${state.prazo_dias} dias ≈ ${semanasTotais()} semanas · meta do plano: ${Math.round(state.meta_kcal)} kcal/dia · peso-alvo do plano: ${state.peso_alvo_kg.toFixed(1)} kg`
        );
    }

    function escalas(seriePeso) {
        x = d3.scaleLinear().domain([0, semanasTotais()]).range([0, innerW]);

        const kcalVals = pontos.map(p => p.kcal).concat(faixaSegura(), [state.get_kcal]);
        const kMin = Math.min(...kcalVals) - 120;
        const kMax = Math.max(...kcalVals) + 120;
        yKcal = d3.scaleLinear().domain([kMin, kMax]).nice().range([innerH, 0]);

        const pesos = seriePeso.map(p => p.peso);
        const pMin = Math.min(...pesos, state.peso_alvo_kg) - 1.5;
        const pMax = Math.max(...pesos, state.peso_alvo_kg) + 1.5;
        yPeso = d3.scaleLinear().domain([pMin, pMax]).nice().range([innerH, 0]);
    }

    function desenharEixos() {
        const eixoX = d3.axisBottom(x).ticks(Math.min(12, semanasTotais() + 1)).tickFormat(d => "S" + d);
        const eixoYk = d3.axisLeft(yKcal).ticks(8);
        const eixoYp = d3.axisRight(yPeso).ticks(8);

        camadas.eixos.selectAll("*").remove();
        camadas.eixos.append("g").attr("transform", `translate(0,${innerH})`).call(eixoX);
        camadas.eixos.append("g").call(eixoYk);
        camadas.eixos.append("g").attr("transform", `translate(${innerW},0)`).call(eixoYp);

        camadas.eixos.append("text").attr("class", "eixo-label")
            .attr("x", innerW / 2).attr("y", innerH + 32).attr("text-anchor", "middle")
            .text("semanas");
        camadas.eixos.append("text").attr("class", "eixo-label")
            .attr("x", -innerH / 2).attr("y", -52).attr("text-anchor", "middle")
            .attr("transform", "rotate(-90)").text("kcal/dia");
        camadas.eixos.append("text").attr("class", "eixo-label")
            .attr("x", innerW / 2).attr("y", -12).attr("text-anchor", "middle")
            .attr("transform", `translate(${innerW - 30},0) rotate(90)`)
            .text("peso (kg)");
    }

    function desenharZonaSegura() {
        const [min, max] = faixaSegura();
        camadas.zona.selectAll("*").remove();
        camadas.zona.append("rect")
            .attr("x", 0).attr("width", innerW)
            .attr("y", yKcal(max)).attr("height", Math.max(0, yKcal(min) - yKcal(max)))
            .attr("fill", "#aed6f1").attr("opacity", 0.35);
    }

    function desenharLinhaGet() {
        camadas.get.selectAll("*").remove();
        camadas.get.append("line")
            .attr("x1", 0).attr("x2", innerW)
            .attr("y1", yKcal(state.get_kcal)).attr("y2", yKcal(state.get_kcal))
            .attr("stroke", "#85929e").attr("stroke-width", 1.6)
            .attr("stroke-dasharray", "6 4");
        camadas.get.append("text").attr("class", "eixo-label")
            .attr("x", innerW - 4).attr("y", yKcal(state.get_kcal) - 6).attr("text-anchor", "end")
            .text(`GET ${Math.round(state.get_kcal)}`);
    }

    function desenharIngestao() {
        camadas.ingestao.selectAll("*").remove();

        const linha = d3.line()
            .x(d => x(d.semana)).y(d => yKcal(d.kcal))
            .curve(d3.curveMonotoneX);
        const area = d3.area()
            .x(d => x(d.semana)).y0(innerH).y1(d => yKcal(d.kcal))
            .curve(d3.curveMonotoneX);

        camadas.ingestao.append("path").datum(pontos)
            .attr("d", area).attr("fill", "rgba(26,82,118,0.10)").attr("pointer-events", "none");
        camadas.ingestao.append("path").datum(pontos)
            .attr("d", linha).attr("fill", "none")
            .attr("stroke", "#1a5276").attr("stroke-width", 2.6).attr("pointer-events", "none");

        if (modo === "ingestao") {
            const drag = d3.drag()
                .on("drag", (ev, d) => {
                    d.kcal = clampKcal(yKcal.invert(ev.y));
                    render();
                });
            camadas.ingestao.selectAll("circle.handle")
                .data(pontos).join("circle")
                .attr("class", "handle")
                .attr("cx", d => x(d.semana)).attr("cy", d => yKcal(d.kcal))
                .attr("r", 7).attr("fill", "#154360").attr("stroke", "#fff").attr("stroke-width", 2)
                .call(drag);
        }
    }

    function desenharPeso(serie) {
        camadas.peso.selectAll("*").remove();
        const linha = d3.line()
            .x(d => x(d.semana)).y(d => yPeso(d.peso))
            .curve(d3.curveMonotoneX);

        camadas.peso.append("path").datum(serie)
            .attr("d", linha).attr("fill", "none")
            .attr("stroke", "#2e86c1").attr("stroke-width", 2.2).attr("pointer-events", "none");
        camadas.peso.selectAll("circle.peso-pt")
            .data(serie).join("circle")
            .attr("class", "peso-pt")
            .attr("cx", d => x(d.semana)).attr("cy", d => yPeso(d.peso))
            .attr("r", 3.2).attr("fill", "#2e86c1").attr("pointer-events", "none");

        if (modo === "alvo") {
            const fim = serie[serie.length - 1];
            const drag = d3.drag()
                .on("drag", (ev) => {
                    pesoAlvoAtual = clampPeso(yPeso.invert(ev.y));
                    aplicarIngestaoDoAlvo();
                    render();
                });
            camadas.peso.append("circle").attr("class", "handle")
                .attr("cx", x(fim.semana)).attr("cy", yPeso(pesoAlvoAtual))
                .attr("r", 9).attr("fill", "#2471a3").attr("stroke", "#fff").attr("stroke-width", 2.5)
                .call(drag);
            camadas.peso.append("text").attr("class", "eixo-label")
                .attr("x", x(fim.semana) - 12).attr("y", yPeso(pesoAlvoAtual) - 12)
                .attr("text-anchor", "end").text(`${pesoAlvoAtual.toFixed(1)} kg`);
        }
    }

    function aplicarIngestaoDoAlvo() {
        const alvo = pesoAlvoAtual;
        const kcal = ingestaoConstanteParaPeso(alvo);
        pontos = pontos.map(p => ({ semana: p.semana, kcal: clampKcal(kcal) }));
    }

    function render() {
        const serie = projetarPeso();
        escalas(serie);
        desenharEixos();
        desenharZonaSegura();
        desenharLinhaGet();
        desenharIngestao();
        desenharPeso(serie);
        atualizarMetricas();
    }

    function montarSvg() {
        d3.select("#grafico").selectAll("svg").remove();
        svg = d3.select("#grafico").append("svg")
            .attr("width", W).attr("height", H)
            .attr("viewBox", `0 0 ${W} ${H}`);

        camadas = {
            zona: svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`),
            get: svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`),
            overlay: svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`),
            ingestao: svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`),
            peso: svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`),
            eixos: svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`),
        };

        // Tooltip: semana mais próxima do mouse
        camadas.overlay.append("rect")
            .attr("width", innerW).attr("height", innerH)
            .attr("fill", "transparent")
            .on("mousemove", (ev) => {
                const [mx] = d3.pointer(ev);
                const sem = Math.max(0, Math.round(x.invert(mx)));
                const dia = Math.min(state.prazo_dias, Math.round(sem * 7));
                const kcal = kcalNoDia(dia);
                const peso = pesoProjetadoNoDia(dia);
                tooltip
                    .style("left", (ev.pageX + 16) + "px")
                    .style("top", (ev.pageY + 8) + "px")
                    .style("opacity", 1)
                    .html(
                        `<b>Semana ${sem}</b> (dia ${dia})<br>` +
                        `Ingestão: <b>${Math.round(kcal)}</b> kcal/dia<br>` +
                        `Balanço: <b>${(kcal - state.get_kcal) >= 0 ? "+" : ""}${Math.round(kcal - state.get_kcal)}</b> kcal/dia<br>` +
                        `Peso projetado: <b>${peso.toFixed(1)}</b> kg`
                    );
            })
            .on("mouseleave", () => tooltip.style("opacity", 0));
    }

    function pesoProjetadoNoDia(dia) {
        let peso = state.peso_atual_kg;
        for (let d = 1; d <= dia; d++) peso += (kcalNoDia(d) - state.get_kcal) / KCAL_POR_KG;
        return peso;
    }

    // ══════════════════════════════════════════════════════════════════
    // Inicialização / ações
    // ══════════════════════════════════════════════════════════════════

    function inicializarPontos() {
        const n = semanasTotais();
        pontos = [];
        for (let s = 0; s <= n; s++) {
            pontos.push({ semana: s, kcal: Math.round(state.meta_kcal) });
        }
        pesoAlvoAtual = state.peso_alvo_kg;
    }

    async function carregar() {
        const res = await fetch(cfg.dadosUrl);
        if (!res.ok) throw new Error("Falha ao carregar dados do simulador");
        state = await res.json();
        inicializarPontos();
        montarSvg();
        render();
    }

    async function aplicar() {
        const serie = projetarPeso();
        const fim = serie[serie.length - 1].peso;
        const media = Math.round(mediaIngestao());
        const balanco = Math.round(media - state.get_kcal);

        const payload = {
            meta_kcal: media,
            deficit_diario_kcal: balanco,
            peso_alvo_kg: modo === "alvo" ? pesoAlvoAtual : fim,
        };

        const msg = d3.select("#sim-mensagem");
        try {
            const res = await fetch(cfg.patchUrl, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.erro || "Erro ao aplicar estratégia");

            state = { ...state, ...payload, meta_kcal: body.meta_kcal, peso_alvo_kg: body.peso_alvo_kg };
            inicializarPontos();
            render();
            msg.attr("class", "ok").html(
                `✅ Estratégia aplicada ao plano #${cfg.planoId}: meta <b>${body.meta_kcal}</b> kcal/dia, ` +
                `balanço <b>${body.deficit_diario_kcal >= 0 ? "+" : ""}${body.deficit_diario_kcal}</b> kcal/dia, ` +
                `peso-alvo <b>${body.peso_alvo_kg}</b> kg. ` +
                `Macros recalculadas (${body.proteinas_g}/${body.carboidratos_g}/${body.lipidios_g} g). ` +
                `<a href="/planos/${cfg.planoId}" style="color:#1a5276;">Ir para o plano →</a>`
            );
        } catch (e) {
            msg.attr("class", "erro").html(`⚠️ ${e.message}`);
        }
    }

    async function restaurar() {
        const msg = d3.select("#sim-mensagem").attr("class", "");
        msg.html("");
        await carregar();
    }

    // ── Eventos ───────────────────────────────────────────────────────
    d3.selectAll("input[name=modo]").on("change", function () {
        modo = this.value;
        if (modo === "alvo") {
            // ponto de partida: peso-alvo atual do plano; ingestão constante
            pesoAlvoAtual = state.peso_alvo_kg;
            aplicarIngestaoDoAlvo();
        }
        // ao voltar para "ingestao", preserva a curva atual (já é a solução
        // do modo alvo) — o usuário continua ajustando de onde parou
        render();
    });

    // ── Export ────────────────────────────────────────────────────────
    window.Simulador = { carregar, aplicar, restaurar };

    carregar().catch(e => {
        d3.select("#sim-mensagem").attr("class", "erro").html(`⚠️ ${e.message}`);
    });
})();
