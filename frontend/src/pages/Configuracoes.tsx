import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Config } from "../api";
import { Carregando, ErroBox, useToast } from "../components/ui";

export default function Configuracoes() {
  const { data, isLoading, error } = useQuery({ queryKey: ["config"], queryFn: () => api.get<Config>("/config") });
  const [chave, setChave] = useState("");
  const [modelo, setModelo] = useState("");
  const [erro, setErro] = useState<unknown>(null);
  const qc = useQueryClient();
  const toast = useToast();

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await api.put("/config/gemini", { api_key: chave.trim() || undefined, modelo: modelo.trim() || undefined });
      setChave("");
      qc.invalidateQueries({ queryKey: ["config"] });
      toast("Configuração salva");
    } catch (err) { setErro(err); }
  }

  if (isLoading) return <Carregando />;
  if (error || !data) return <ErroBox erro={error} />;
  return (
    <>
      <div className="topo"><div><h1>Configurações</h1><p className="sub">IA usada na importação de arquivos</p></div></div>
      <section className="card" style={{ maxWidth: 720 }}>
        <h2>Google Gemini</h2>
        <p>
          Situação:{" "}
          {data.gemini_configurado
            ? <span className="pill st-em_uso">Chave configurada ({data.gemini_chave_mascarada})</span>
            : <span className="pill st-com_defeito">Sem chave</span>}
          {" "}· modelo <code>{data.gemini_modelo}</code>
        </p>
        <p className="muted">
          Crie uma chave gratuita em aistudio.google.com/apikey. Ela fica salva no arquivo <code>backend/.env</code> deste computador.
        </p>
        <div className="aviso atencao">
          No plano gratuito o Google pode usar o conteúdo enviado para melhorar os produtos dele. Para planilhas reais
          com IPs internos, confirme com a TI ou use o método “Regras”, que não envia nada para fora.
        </div>
        <form className="form" onSubmit={salvar}>
          <div className="form-grid">
            <label className="campo" htmlFor="cfg-chave"><span>Nova chave da API</span>
              <input id="cfg-chave" type="password" autoComplete="off" value={chave} onChange={(e) => setChave(e.target.value)} placeholder="AIza…" />
            </label>
            <label className="campo" htmlFor="cfg-modelo"><span>Modelo</span>
              <input id="cfg-modelo" className="mono" value={modelo} onChange={(e) => setModelo(e.target.value)} placeholder={data.gemini_modelo} />
            </label>
          </div>
          <ErroBox erro={erro} />
          <div className="acoes"><button className="primario" disabled={!chave.trim() && !modelo.trim()}>Salvar</button></div>
        </form>
      </section>
    </>
  );
}
