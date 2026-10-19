import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { PageHeader } from "./components/PageHeader";
import { Panel } from "./components/Panel";
import { NAV_GROUPS } from "./lib/navigation";
import { BackendDetail } from "./pages/BackendDetail";
import { Backends } from "./pages/Backends";
import { Inference } from "./pages/Inference";
import { Keys } from "./pages/Keys";
import { Overview } from "./pages/Overview";
import { RequestDetail } from "./pages/RequestDetail";
import { Requests } from "./pages/Requests";
import { Routing } from "./pages/Routing";

function NotFound() {
  return (
    <main className="page">
      <PageHeader title="页面不存在" lead="以下路由是当前控制层契约里已接入的入口。" />
      <Panel title="可用入口">
        <div className="stack">
          {NAV_GROUPS.map((group) => (
            <div className="row" key={group.label}>
              <span className="faint">{group.label}</span>
              {group.items.map((item) => (
                <Link key={item.to} to={item.to}>
                  {item.label}
                </Link>
              ))}
            </div>
          ))}
        </div>
      </Panel>
    </main>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/backends" element={<Backends />} />
          <Route path="/backends/:backendId" element={<BackendDetail />} />
          <Route path="/keys" element={<Keys />} />
          <Route path="/routing" element={<Routing />} />
          <Route path="/inference" element={<Inference />} />
          <Route path="/requests" element={<Requests />} />
          <Route path="/requests/:requestId" element={<RequestDetail />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
