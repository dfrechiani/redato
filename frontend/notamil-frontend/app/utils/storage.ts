export const clearLocalStorage = () => {
  // Limpa todos os dados do usuário
  localStorage.removeItem('user_id');
  localStorage.removeItem('user_role');
  localStorage.removeItem('user_name');
  localStorage.removeItem('class_id');
  localStorage.removeItem('school_id');
  
  // Limpa dados específicos da aplicação
  localStorage.removeItem('ocrPreFillContent');
  localStorage.removeItem('ocrPreFillTheme');
  localStorage.removeItem('correctionData');
};

export const saveUserData = (userData: {
  user_id: string;
  role: string;
  name: string;
  class_id?: string;
  school_id?: string;
}) => {
  // Primeiro limpa o localStorage
  clearLocalStorage();
  
  // Depois salva os novos dados
  localStorage.setItem('user_id', userData.user_id);
  localStorage.setItem('user_role', userData.role);
  localStorage.setItem('user_name', userData.name);
  
  if (userData.class_id) {
    localStorage.setItem('class_id', userData.class_id);
  }
  
  if (userData.school_id) {
    localStorage.setItem('school_id', userData.school_id);
  }
}; 