import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Dashboard as DashboardT } from "./api";
import Dashboard from "./pages/Dashboard";
import Objetos from "./pages/Objetos";
import ObjetoForm from "./pages/ObjetoForm";
import ObjetoFicha from "./pages/ObjetoFicha";
import Categorias from "./pages/Categorias";
import Unidades from "./pages/Unidades";
import Pessoas from "./pages/Pessoas";
import Importar from "./pages/Importar";
import ImportacaoRevisao from "./pages/ImportacaoRevisao";
import Configuracoes from "./pages/Configuracoes";

export default function App() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<DashboardT>("/dashboard") });
  const pendentes = dash.data?.itens_pendentes_revisao ?? 0;
  return (
    <div className="shell">
      <aside className="side">
        <div className="marca"><span className="etq">PAT</span><b>Patrimônio</b></div>
        <nav className="nav" aria-label="Principal">
          <NavLink to="/" end>Painel</NavLink>
          <NavLink to="/objetos">Objetos</NavLink>
          <NavLink to="/importar">Importar{pendentes > 0 && <span className="badge" title="Itens aguardando revisão">{pendentes}</span>}</NavLink>
          <NavLink to="/arquivados">Arquivados</NavLink>
          <span className="grupo">Cadastros</span>
          <NavLink to="/categorias">Categorias</NavLink>
          <NavLink to="/unidades">Unidades e setores</NavLink>
          <NavLink to="/pessoas">Pessoas</NavLink>
          <NavLink to="/configuracoes">Configurações</NavLink>
        </nav>
        <p className="rodape">Rodando localmente · sem login</p>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/objetos" element={<Objetos />} />
          <Route path="/arquivados" element={<Objetos arquivados />} />
          <Route path="/objetos/novo" element={<ObjetoForm />} />
          <Route path="/objetos/:id" element={<ObjetoFicha />} />
          <Route path="/objetos/:id/editar" element={<ObjetoForm />} />
          <Route path="/categorias" element={<Categorias />} />
          <Route path="/unidades" element={<Unidades />} />
          <Route path="/pessoas" element={<Pessoas />} />
          <Route path="/importar" element={<Importar />} />
          <Route path="/importar/:id" element={<ImportacaoRevisao />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
