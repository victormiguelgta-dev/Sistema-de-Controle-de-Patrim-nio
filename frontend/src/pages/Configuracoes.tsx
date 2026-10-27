import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Config } from "../api";
import { Carregando, ErroBox, useToast } from "../components/ui";

const MODELOS_SUGERIDOS = [
  { nome: "qwen2.5:7b", texto: "Recomendado. Bom para extrair dados e responder em formato estruturado; ~4,7 GB." },
  { nome: "qwen2.5:3b", texto: "Mais leve, para computador sem placa de vídeo; acerta um pouco menos. ~1,9 GB." },
  { nome: "llama3.1:8b", texto: "Alternativa do mesmo porte do recomendado. ~4,9 GB." },
];

function Copiar({ texto }: { texto: string }) {
  const toast = useToast();
  return (
    <span className="acoes" style={{ gap: 6 }}>
      <code style={{ background: "var(--surface-2)", padding: "6px 10px", borderRadius: 8 }}>{texto}</code>
      <button type="button" className="pequeno" onClick={() => navigator.clipboard?.writeText(texto).then(() => toast("Copiado"), () => {})}>
        Copiar
      </button>
    </span>
  );
}

export default function Configuracoes() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data, isLoading, error, refetch, isFetching } = useQuery({ queryKey: ["config"], queryFn: () => api.get<Config>("/config") });
  const [modeloOllama, setModeloOllama] = useState("");
  const [urlOllama, setUrlOllama] = useState("");
  const [chave, setChave] = useState("");
  const [modeloGemini, setModeloGemini] = useState("");
  const [erro, setErro] = useState<unknown>(null);

  async function salvar(corpo: Record<string, string | undefined>, msg: string) {
    setErro(null);
    try {
      await api.put("/config/ia", corpo);
      qc.invalidateQueries({ queryKey: ["config"] });
      toast(msg);
      return true;
    } catch (err) { setErro(err); return false; }
  }

  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;
  const modeloAtual = data.ollama_modelo;
  const instalado = (nome: string) => data.ollama_modelos.some((m) => m === nome || m === `${nome}:latest`);

  return (
    <>
      <div className="topo">
        <div><h1>Configurações</h1><p className="sub">IA usada na importação de arquivos</p></div>
        <button onClick={() => refetch()} disabled={isFetching}>{isFetching ? "Verificando…" : "Verificar de novo"}</button>
      </div>

      <section className="card" style={{ maxWidth: 820 }}>
        <header><div><h2>Qual IA usar</h2><p>Os métodos “Regras” e “Mapear colunas” funcionam sem IA, com qualquer escolha.</p></div></header>
        <div className="metodos" role="radiogroup" aria-label="Provedor de IA">
          {([
            ["ollama", "Ollama · modelo local", "Roda neste computador. Nada sai da máquina, sem custo e sem limite de uso. Precisa de ~8 GB de RAM livres."],
            ["gemini", "Gemini · nuvem do Google", "Acerta mais em textos bagunçados. O texto vai para o Google; no plano gratuito ele pode usar o conteúdo."],
          ] as const).map(([id, titulo, texto]) => (
            <label key={id} className={"metodo" + (data.ia_provedor === id ? " sel" : "")}>
              <span className="check" style={{ color: "var(--fg)" }}>
                <input type="radio" name="provedor" checked={data.ia_provedor === id}
                  onChange={() => salvar({ provedor: id }, `Agora usando ${id === "ollama" ? "o Ollama" : "o Gemini"}`)} />
                <b>{titulo}</b>
              </span>
              <span>{texto}</span>
            </label>
          ))}
        </div>
        {data.ia_pronta
          ? <div className="aviso info">Pronto para importar com IA.</div>
          : <div className="aviso atencao">{data.ia_problema}</div>}
        <ErroBox erro={erro} />
      </section>

      {data.ia_provedor === "ollama" && (
        <section className="card" style={{ maxWidth: 820 }}>
          <header>
            <div><h2>Ollama</h2><p>Servidor local em <code>{data.ollama_url}</code></p></div>
            {data.ollama_rodando
              ? <span className="pill st-em_uso">Rodando · {data.ollama_modelos.length} modelo(s)</span>
              : <span className="pill st-com_defeito">Não encontrado</span>}
          </header>

          {!data.ollama_rodando && (
            <ol style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 10 }}>
              <li>Baixe e instale o Ollama em <a href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com/download</a> (Windows, Mac ou Linux).</li>
              <li>Abra o Ollama. Ele fica rodando em segundo plano.</li>
              <li>Baixe o modelo no terminal: <Copiar texto={`ollama pull ${modeloAtual}`} /></li>
              <li>Volte aqui e clique em <b>Verificar de novo</b>.</li>
            </ol>
          )}

          {data.ollama_rodando && !instalado(modeloAtual) && (
            <div className="aviso atencao" style={{ display: "grid", gap: 8 }}>
              <span>O modelo <b>{modeloAtual}</b> ainda não foi baixado. Rode no terminal e depois clique em Verificar de novo:</span>
              <Copiar texto={`ollama pull ${modeloAtual}`} />
            </div>
          )}

          <div style={{ display: "grid", gap: 8 }}>
            <h3>Modelo</h3>
            {MODELOS_SUGERIDOS.map((m) => (
              <label key={m.nome} className="check" style={{ alignItems: "flex-start" }}>
                <input type="radio" name="modelo-ollama" checked={modeloAtual === m.nome} style={{ marginTop: 4 }}
                  onChange={() => salvar({ ollama_modelo: m.nome }, `Modelo ${m.nome} selecionado`)} />
                <span>
                  <b>{m.nome}</b>{instalado(m.nome) ? <span className="chip" style={{ marginLeft: 8 }}>baixado</span> : null}
                  <br /><span className="muted" style={{ fontWeight: 400 }}>{m.texto}</span>
                </span>
              </label>
            ))}
            {data.ollama_modelos.filter((m) => !MODELOS_SUGERIDOS.some((s) => m === s.nome)).map((m) => (
              <label key={m} className="check">
                <input type="radio" name="modelo-ollama" checked={modeloAtual === m} onChange={() => salvar({ ollama_modelo: m }, `Modelo ${m} selecionado`)} />
                <span><b>{m}</b> <span className="chip">baixado</span></span>
              </label>
            ))}
          </div>

          <details>
            <summary className="muted" style={{ cursor: "pointer" }}>Outro modelo ou endereço</summary>
            <form className="form" style={{ marginTop: 12 }} onSubmit={async (e: FormEvent) => {
              e.preventDefault();
              if (await salvar({ ollama_modelo: modeloOllama.trim() || undefined, ollama_url: urlOllama.trim() || undefined }, "Configuração salva")) {
                setModeloOllama(""); setUrlOllama("");
              }
            }}>
              <div className="form-grid">
                <label className="campo" htmlFor="cfg-om"><span>Nome do modelo</span>
                  <input id="cfg-om" className="mono" value={modeloOllama} onChange={(e) => setModeloOllama(e.target.value)} placeholder="ex.: gemma3:4b" />
                </label>
                <label className="campo" htmlFor="cfg-ou"><span>Endereço do Ollama</span>
                  <input id="cfg-ou" className="mono" value={urlOllama} onChange={(e) => setUrlOllama(e.target.value)} placeholder={data.ollama_url} />
                </label>
              </div>
              <div className="acoes"><button className="primario" disabled={!modeloOllama.trim() && !urlOllama.trim()}>Salvar</button></div>
            </form>
          </details>
        </section>
      )}

      {data.ia_provedor === "gemini" && (
        <section className="card" style={{ maxWidth: 820 }}>
          <header>
            <div><h2>Google Gemini</h2><p>Modelo <code>{data.gemini_modelo}</code></p></div>
            {data.gemini_configurado
              ? <span className="pill st-em_uso">Chave configurada ({data.gemini_chave_mascarada})</span>
              : <span className="pill st-com_defeito">Sem chave</span>}
          </header>
          <p className="muted">Crie uma chave gratuita em aistudio.google.com/apikey. Ela fica salva no arquivo <code>backend/.env</code> deste computador.</p>
          <div className="aviso atencao">
            No plano gratuito o Google pode usar o conteúdo enviado para melhorar os produtos, e pessoas da equipe dele podem lê-lo.
            Para planilhas reais com IPs internos, use o Ollama ou os métodos sem IA.
          </div>
          <form className="form" onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            if (await salvar({ gemini_api_key: chave.trim() || undefined, gemini_modelo: modeloGemini.trim() || undefined }, "Configuração salva")) {
              setChave(""); setModeloGemini("");
            }
          }}>
            <div className="form-grid">
              <label className="campo" htmlFor="cfg-chave"><span>Nova chave da API</span>
                <input id="cfg-chave" type="password" autoComplete="off" value={chave} onChange={(e) => setChave(e.target.value)} placeholder="AIza…" />
              </label>
              <label className="campo" htmlFor="cfg-modelo"><span>Modelo</span>
                <input id="cfg-modelo" className="mono" value={modeloGemini} onChange={(e) => setModeloGemini(e.target.value)} placeholder={data.gemini_modelo} />
              </label>
            </div>
            <div className="acoes"><button className="primario" disabled={!chave.trim() && !modeloGemini.trim()}>Salvar</button></div>
          </form>
        </section>
      )}
    </>
  );
}
