import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AgentsPage from "./pages/AgentsPage";
import NewProjectPage from "./pages/NewProjectPage";
import ProjectPage from "./pages/ProjectPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<NewProjectPage />} />
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="/agents" element={<AgentsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
