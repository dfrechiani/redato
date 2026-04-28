import axios from 'axios';

const api = axios.create({
  baseURL: window.ENV?.NEXT_PUBLIC_API_BASE_URL,
  // Se você quiser configurar headers globais, interceptors etc., pode fazer aqui
  // headers: {
  //   'Content-Type': 'application/json',
  // },
});

export default api;
