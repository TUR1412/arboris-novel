// AIMETA P=认证状态_用户登录状态管理|R=token_user_login_logout|NR=不含API调用|E=store:auth|X=internal|A=useAuthStore|D=pinia|S=storage|RD=./README.ai
import { defineStore } from 'pinia';
import { API_BASE_URL } from '@/api/novel';

const API_URL = `${API_BASE_URL}/api/auth`;
const LOCAL_SINGLE_USER_TOKEN = 'local-single-user';

interface AuthOptions {
  // 是否允许用户自助注册
  allow_registration: boolean;
  // 是否启用 Linux.do 登录
  enable_linuxdo_login: boolean;
}

// Helper function to handle fetch requests and token refreshing
async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const authStore = useAuthStore();
  const headers = new Headers(options.headers || {});
  
  if (authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`);
  }

  options.headers = headers;
  const response = await fetch(url, options);

  const refreshedToken = response.headers.get('X-Token-Refresh');
  if (refreshedToken) {
    authStore.token = refreshedToken;
    localStorage.setItem('token', refreshedToken);
  }

  return response;
}

interface User {
  id: number;
  username: string;
  is_admin: boolean;
  must_change_password: boolean;
}

const createLocalUser = (): User => ({
  id: 1,
  username: 'admin',
  is_admin: true,
  must_change_password: false,
});

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: LOCAL_SINGLE_USER_TOKEN as string | null,
    user: createLocalUser() as User | null,
    authOptions: {
      allow_registration: false,
      enable_linuxdo_login: false,
    } as AuthOptions | null,
    authOptionsLoaded: true,
  }),
  getters: {
    isAuthenticated: () => true,
    allowRegistration: (state) => state.authOptions?.allow_registration ?? false,
    enableLinuxdoLogin: (state) => state.authOptions?.enable_linuxdo_login ?? false,
    mustChangePassword: (state) => state.user?.must_change_password ?? false,
  },
  actions: {
    ensureLocalSession() {
      this.token = LOCAL_SINGLE_USER_TOKEN;
      localStorage.setItem('token', LOCAL_SINGLE_USER_TOKEN);
      if (!this.user) {
        this.user = createLocalUser();
      }
    },
    async fetchAuthOptions(force = false) {
      if (this.authOptionsLoaded && !force) {
        return;
      }
      this.ensureLocalSession();
      this.authOptions = {
        allow_registration: false,
        enable_linuxdo_login: false,
      };
      this.authOptionsLoaded = true;
    },
    async login(username: string, password: string): Promise<boolean> {
      await this.fetchUser();
      return false;
    },
    async register(payload: { username: string; email: string; password: string; verification_code: string }) {
      void payload;
      throw new Error('本地单用户模式已关闭注册功能');
    },
    logout() {
      this.ensureLocalSession();
    },
    async fetchUser() {
      this.ensureLocalSession();
      try {
        const response = await fetchWithAuth(`${API_URL}/users/me`);

        if (!response.ok) {
          throw new Error('Failed to fetch user');
        }

        const userData = await response.json();
        this.user = {
          id: userData.id,
          username: userData.username,
          is_admin: userData.is_admin || true,
          must_change_password: false,
        };
      } catch (error) {
        console.warn('读取本地管理员信息失败，将使用默认本地身份', error);
        this.user = createLocalUser();
      }
    },
  },
});
