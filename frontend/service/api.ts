// client/src/service/api.ts

const BASE_URL = "http://127.0.0.1:5000"; // Đảm bảo backend chạy port này

export const API_URLS = {
  LOGIN: `${BASE_URL}/login`,
  LOGOUT: `${BASE_URL}/api/logout`,
  ME: `${BASE_URL}/api/me`,
  LOGS: `${BASE_URL}/api/logs`,

  // Link cũ (có thể giữ lại nếu cần)
  EMPLOYEES: `${BASE_URL}/api/employees`,

  // 1. Link lấy danh sách nhân viên
  USERS: `${BASE_URL}/nguoi_dung`,

  // 2. Link sửa nhân viên
  UPDATE_USER: `${BASE_URL}/api/update_employee`,

  // 3. Link thêm mới nhân viên
  ADD_USER: `${BASE_URL}/api/add_employee`,

  // 4. Link xóa nhân viên (MỚI THÊM CHO KHỚP BACKEND)
  DELETE_USER: `${BASE_URL}/api/delete_employee`,

  // Hàm tạo link stream video
  STREAM: (id: number) => `${BASE_URL}/video_feed/${id}`,
};

export const api = {
  // --- 1. AUTHENTICATION ---
  login: async (username: string, password: string) => {
    try {
      const res = await fetch(API_URLS.LOGIN, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Lỗi đăng nhập");
      return data;
    } catch (error) {
      console.error("Login error:", error);
      throw error;
    }
  },

  logout: async () => {
    try {
      await fetch(API_URLS.LOGOUT, {
        method: "POST",
        credentials: "include",
      });
      return { success: true };
    } catch (error) {
      return { success: false };
    }
  },

  getMe: async () => {
    try {
      const res = await fetch(API_URLS.ME, { credentials: "include" });
      if (!res.ok) return { authenticated: false };
      return await res.json();
    } catch (error) {
      return { authenticated: false };
    }
  },

  // --- 2. DATA (LOGS & DASHBOARD) ---
  getLogs: async () => {
    try {
      const res = await fetch(API_URLS.LOGS, { credentials: "include" });
      if (!res.ok) return [];
      return await res.json();
    } catch (error) {
      console.error("Get Logs error:", error);
      return [];
    }
  },

  // --- 3. QUẢN LÝ NHÂN VIÊN ---

  // Lấy danh sách
  getUsers: async () => {
    try {
      const res = await fetch(API_URLS.USERS, { method: "GET" });
      const data = await res.json();
      if (!res.ok) return [];
      return Array.isArray(data) ? data : data.data || [];
    } catch (error) {
      console.error("Get users error:", error);
      return [];
    }
  },

  // Thêm nhân viên mới
  addUser: async (userData: any) => {
    try {
      const res = await fetch(API_URLS.ADD_USER, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(userData),
      });
      return await res.json();
    } catch (error) {
      console.error("Lỗi thêm mới:", error);
      return { success: false, message: "Lỗi kết nối server" };
    }
  },

  // Cập nhật thông tin
  updateUser: async (userData: any) => {
    try {
      const res = await fetch(API_URLS.UPDATE_USER, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(userData),
      });
      return await res.json();
    } catch (error) {
      console.error("Lỗi update:", error);
      return { success: false, message: "Lỗi kết nối server" };
    }
  },

  // Xóa nhân viên (ĐÃ SỬA: Dùng ma_nv thay vì name)
  deleteUser: async (ma_nv: number) => {
    try {
      const res = await fetch(API_URLS.DELETE_USER, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ma_nv }), // Gửi ID đi để xóa chính xác
      });
      return await res.json();
    } catch (error) {
      console.error("Lỗi xóa:", error);
      return { success: false, message: "Lỗi kết nối server" };
    }
  },

  // (Giữ lại hàm cũ để tương thích ngược nếu cần, nhưng khuyên dùng deleteUser ở trên)
  addEmployee: async (formData: FormData) => {
    try {
      const res = await fetch(API_URLS.EMPLOYEES, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message);
      return data;
    } catch (error) {
      throw error;
    }
  },
};
