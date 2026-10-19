import { Outlet } from "react-router-dom";

import { ApiKeyBar } from "./ApiKeyBar";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function Layout() {
  return (
    <div className="shell">
      <Sidebar />
      <div className="main">
        <Topbar />
        <ApiKeyBar />
        <Outlet />
      </div>
    </div>
  );
}
