import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearApiKey,
  getApiKey,
  maskApiKey,
  setApiKey,
  subscribeApiKey,
} from "./apiKey";

const STORAGE_KEY = "ai-infra.api-key";

describe("apiKey store", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    setApiKey("");
  });

  it("未设置时返回空字符串", () => {
    expect(getApiKey()).toBe("");
  });

  it("设置后能读回，并落到 sessionStorage", () => {
    setApiKey("aip_abcdefghijklmnopqrstuvwxyz0123456789ABCD");
    expect(getApiKey()).toBe("aip_abcdefghijklmnopqrstuvwxyz0123456789ABCD");
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBe(
      "aip_abcdefghijklmnopqrstuvwxyz0123456789ABCD",
    );
  });

  it("去掉首尾空白，避免粘贴时多带换行", () => {
    setApiKey("  aip_trimmed  \n");
    expect(getApiKey()).toBe("aip_trimmed");
  });

  it("清除后 sessionStorage 里也不留", () => {
    setApiKey("aip_tobecleared");
    clearApiKey();
    expect(getApiKey()).toBe("");
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("首次读取时从 sessionStorage 恢复", async () => {
    window.sessionStorage.setItem(STORAGE_KEY, "aip_fromstorage");
    vi.resetModules();
    const fresh = await import("./apiKey");
    expect(fresh.getApiKey()).toBe("aip_fromstorage");
  });

  it("订阅者只在变更时被通知，退订后不再收到", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeApiKey(listener);

    setApiKey("aip_first");
    expect(listener).toHaveBeenCalledTimes(1);

    setApiKey("aip_second");
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    setApiKey("aip_third");
    expect(listener).toHaveBeenCalledTimes(2);
  });
});

describe("maskApiKey", () => {
  it("空值返回空", () => {
    expect(maskApiKey("")).toBe("");
  });

  it("短值原样返回，不泄露也不误导", () => {
    expect(maskApiKey("aip_short")).toBe("aip_short");
  });

  it("长值只留头 8 位与尾 4 位", () => {
    const masked = maskApiKey("aip_7PxX1234567890abcdefghijklmnopqrstuvwXYZ");
    expect(masked).toBe("aip_7PxX…wXYZ");
    expect(masked.length).toBeLessThan(20);
  });
});
