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
import {
  IconeArquivo, IconeCategorias, IconeConfig, IconeImportar, IconeObjetos, IconePainel, IconePessoas, IconeUnidades,
} from "./components/icones";

export default function App() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<DashboardT>("/dashboard") });
  const pendentes = dash.data?.itens_pendentes_revisao ?? 0;
  return (
    <div className="shell">
      <aside className="side">
        <div className="marca"><span className="logo" aria-hidden>P</span><div><b>Patrimônio</b><small>controle de bens</small></div></div>
        <nav className="nav" aria-label="Principal">
          <NavLink to="/" end><IconePainel />Painel</NavLink>
          <NavLink to="/objetos"><IconeObjetos />Objetos</NavLink>
          <NavLink to="/importar"><IconeImportar />Importar{pendentes > 0 && <span className="badge" title="Itens aguardando revisão">{pendentes}</span>}</NavLink>
          <NavLink to="/arquivados"><IconeArquivo />Arquivados</NavLink>
          <span className="grupo">Cadastros</span>
          <NavLink to="/categorias"><IconeCategorias />Categorias</NavLink>
          <NavLink to="/unidades"><IconeUnidades />Unidades e setores</NavLink>
          <NavLink to="/pessoas"><IconePessoas />Pessoas</NavLink>
          <NavLink to="/configuracoes"><IconeConfig />Configurações</NavLink>
        </nav>
        <p className="rodape">Uso local · sem login</p>
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
