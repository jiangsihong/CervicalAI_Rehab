const DEFAULT_API_BASE = "http://127.0.0.1:5000";
const DEFAULT_TIMEOUT = 20000;

export class ApiError extends Error {
  constructor(message, status = 0, payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function cleanBaseUrl(value) {
  const candidate = String(value || "").trim() || DEFAULT_API_BASE;
  return candidate.replace(/\/+$/, "");
}

export class ApiClient {
  constructor() {
    this.baseUrl = cleanBaseUrl(localStorage.getItem("cervical_api_base"));
    this.timeout = Number(localStorage.getItem("cervical_api_timeout")) || DEFAULT_TIMEOUT;
    this.token = localStorage.getItem("cervical_access_token") || "";
  }

  configure({ baseUrl, timeout }) {
    this.baseUrl = cleanBaseUrl(baseUrl);
    this.timeout = Math.max(3000, Math.min(Number(timeout) || DEFAULT_TIMEOUT, 120000));
    localStorage.setItem("cervical_api_base", this.baseUrl);
    localStorage.setItem("cervical_api_timeout", String(this.timeout));
  }

  setToken(token) {
    this.token = token || "";
    if (this.token) {
      localStorage.setItem("cervical_access_token", this.token);
    } else {
      localStorage.removeItem("cervical_access_token");
    }
  }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), options.timeout || this.timeout);
    const headers = new Headers(options.headers || {});

    if (this.token && options.auth !== false) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: options.method || "GET",
        headers,
        body,
        signal: controller.signal,
      });

      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

      if (!response.ok || (payload && typeof payload === "object" && payload.success === false)) {
        const rawMessage = payload && typeof payload === "object"
          ? payload.message || payload.error
          : "";
        throw new ApiError(this.friendlyMessage(rawMessage, response.status), response.status, payload);
      }

      if (payload && typeof payload === "object" && "data" in payload) {
        return payload.data;
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new ApiError("请求超时，请检查后端连接", 0);
      }
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError("无法连接后端服务", 0, error);
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  friendlyMessage(message, status) {
    const text = String(message || "");
    if (/assessments.*doesn.?t exist|Table .*assessments/i.test(text)) {
      return "评估记录服务尚未就绪，请重启后端后重试";
    }
    if (status >= 500) {
      return text || "服务暂时不可用，请稍后重试";
    }
    if (status === 401) {
      return text || "登录状态已失效，请重新登录";
    }
    if (status === 403) {
      return text || "当前账号没有操作权限";
    }
    return text || `请求失败（${status || "网络错误"}）`;
  }

  register(payload) {
    return this.request("/api/user/register", { method: "POST", body: payload, auth: false });
  }

  login(payload) {
    return this.request("/api/user/login", { method: "POST", body: payload, auth: false });
  }

  sendEmailCode(payload) {
    return this.request("/api/user/email-code", { method: "POST", body: payload, auth: false, timeout: 40000 });
  }

  getProfile() {
    return this.request("/api/user/profile");
  }

  updateProfile(payload) {
    return this.request("/api/user/profile", { method: "PUT", body: payload });
  }

  changePassword(payload) {
    return this.request("/api/user/change-password", { method: "POST", body: payload });
  }

  getUsers(params = {}) {
    return this.request(`/api/user/list${queryString(params)}`);
  }

  getUser(userId) {
    return this.request(`/api/user/${encodeURIComponent(userId)}`);
  }

  getUserStats() {
    return this.request("/api/user/stats");
  }

  getPoseStatus() {
    return this.request("/api/assessment/pose/status", { auth: false, timeout: 8000 });
  }

  estimateImage(file, { annotated = true, confidenceThreshold = "" } = {}) {
    const formData = new FormData();
    formData.append("image", file);
    const params = {
      annotated: annotated ? "true" : "false",
    };
    if (confidenceThreshold !== "") {
      params.confidence_threshold = confidenceThreshold;
    }
    return this.request(`/api/assessment/pose/image${queryString(params)}`, {
      method: "POST",
      body: formData,
      auth: false,
      timeout: 120000,
    });
  }

  submitAssessment(payload) {
    return this.request("/api/assessment/submit", { method: "POST", body: payload });
  }

  getHistory(params = {}) {
    return this.request(`/api/assessment/history${queryString(params)}`);
  }

  saveCameraSession(session, options = {}) {
    return this.request(`/api/assessment/pose/sessions/${encodeURIComponent(session.id)}`, {
      method: "PUT", body: session, ...options,
    });
  }

  getCameraHistory(params = {}) {
    return this.request(`/api/assessment/pose/sessions${queryString(params)}`);
  }

  getCameraSession(id) {
    return this.request(`/api/assessment/pose/sessions/${encodeURIComponent(id)}`);
  }

  getAssessment(assessmentId) {
    return this.request(`/api/assessment/${encodeURIComponent(assessmentId)}`);
  }

  getTrend(days = 30) {
    return this.request(`/api/assessment/trend${queryString({ days })}`);
  }

  getSummary() {
    return this.request("/api/assessment/summary");
  }

  getPatientAssessments(patientId) {
    return this.request(`/api/assessment/patient/${encodeURIComponent(patientId)}`);
  }
}

export function queryString(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}

export { DEFAULT_API_BASE };
