import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles/index.css";

const container = document.getElementById("root");

if (container === null) {
  throw new Error("挂载失败：index.html 中缺少 #root 节点");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
