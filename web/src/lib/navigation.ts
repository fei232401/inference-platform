import { KeyRound, LayoutDashboard, Play, Route, ScrollText, Server } from "lucide-react";
import type { ElementType } from "react";

export type NavItem = {
  to: string;
  label: string;
  icon: ElementType;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: "观测",
    items: [{ to: "/overview", label: "总览", icon: LayoutDashboard }],
  },
  {
    label: "资源",
    items: [
      { to: "/backends", label: "后端实例", icon: Server },
      { to: "/keys", label: "访问密钥", icon: KeyRound },
    ],
  },
  {
    label: "调度",
    items: [
      { to: "/routing", label: "候选打分", icon: Route },
      { to: "/inference", label: "发起推理", icon: Play },
    ],
  },
  {
    label: "追溯",
    items: [{ to: "/requests", label: "请求流水", icon: ScrollText }],
  },
];

const STATIC_TITLES: Record<string, string> = {
  "/overview": "总览",
  "/backends": "后端实例",
  "/routing": "候选打分",
  "/inference": "发起推理",
  "/requests": "请求流水",
  "/keys": "访问密钥",
};

export function resolveTitle(pathname: string): string {
  if (pathname.startsWith("/backends/")) return "实例详情";
  if (pathname.startsWith("/requests/")) return "请求详情";
  return STATIC_TITLES[pathname] ?? "页面不存在";
}
