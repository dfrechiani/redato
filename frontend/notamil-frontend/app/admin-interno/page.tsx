'use client'

import { useState, useEffect } from 'react'
import Layout from '@/app/dashboard/components/Layout'
import { UserCog, Mail, Phone, GraduationCap, Plus, Check, AlertCircle, Users, Trash2, Search, UploadCloud } from 'lucide-react'
import styles from './admin-interno.module.css'
import { Modal, Box, Typography, Button } from '@mui/material';
import { authFetch } from '@/services/authFetch';

interface Professor {
  professor_id: string;
  name: string;
  email: string;
  phone?: string;
}

interface Class {
  class_id: string;
  name: string;
  professor_name?: string;
}

interface Student {
  student_id: string;
  name: string;
  email: string;
  class_id: string;
  class_name: string;
}

export default function AdminInternoDashboard() {
  const [userName, setUserName] = useState('')
  const [loading, setLoading] = useState(true)
  const [professors, setProfessors] = useState<Professor[]>([])
  const [professorLoading, setProfessorLoading] = useState(false)
  const [error, setError] = useState('')
  const [schoolId, setSchoolId] = useState('')
  
  // Estados para criação de turma
  const [className, setClassName] = useState('')
  const [selectedProfessorId, setSelectedProfessorId] = useState('')
  const [isCreatingClass, setIsCreatingClass] = useState(false)
  const [classCreationResult, setClassCreationResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null)
  
  // Estados para listar turmas
  const [classes, setClasses] = useState<Class[]>([])
  const [classLoading, setClassLoading] = useState(false)
  const [classError, setClassError] = useState('')

  // Estados para exclusão de turma
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false)
  const [classToDelete, setClassToDelete] = useState<{ id: string; name: string } | null>(null)
  const [isDeletingClass, setIsDeletingClass] = useState(false)
  const [deleteError, setDeleteError] = useState(''); // Erro específico para exclusão

  // Estado para modal de criação de turma
  const [isCreateClassModalOpen, setIsCreateClassModalOpen] = useState(false);
  
  // Estados para exclusão de PROFESSOR
  const [isConfirmDeleteProfessorModalOpen, setIsConfirmDeleteProfessorModalOpen] = useState(false);
  const [professorToDelete, setProfessorToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeletingProfessor, setIsDeletingProfessor] = useState(false);
  const [deleteProfessorError, setDeleteProfessorError] = useState('');

  // Estados para Alunos e Filtros
  const [students, setStudents] = useState<Student[]>([]); // Lista completa
  const [filteredStudents, setFilteredStudents] = useState<Student[]>([]); // Lista filtrada
  const [studentLoading, setStudentLoading] = useState(false);
  const [studentError, setStudentError] = useState('');
  const [selectedClassFilter, setSelectedClassFilter] = useState(''); // ID da turma para filtro
  const [searchQuery, setSearchQuery] = useState(''); // Termo de pesquisa

  // Estados para exclusão de ALUNO
  const [isConfirmDeleteStudentModalOpen, setIsConfirmDeleteStudentModalOpen] = useState(false);
  const [studentToDelete, setStudentToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeletingStudent, setIsDeletingStudent] = useState(false);
  const [deleteStudentError, setDeleteStudentError] = useState('');

  // Estados para Bulk Register
  const [isBulkRegisterModalOpen, setIsBulkRegisterModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetClassId, setTargetClassId] = useState(''); // ID da turma para vincular
  const [isSubmittingBulk, setIsSubmittingBulk] = useState(false);
  const [bulkRegisterResult, setBulkRegisterResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    // Verificar se o usuário está logado e é admin
    const userId = localStorage.getItem('user_id')
    const userRole = localStorage.getItem('user_role')
    const name = localStorage.getItem('user_name')
    const school = localStorage.getItem('school_id')

    if (!userId || userRole !== 'school_admin') {
      console.error('Usuário não autenticado ou não é admin')
      window.location.href = '/admin-interno-login'
      return
    }

    if (name) {
      setUserName(name)
    }

    if (school) {
      setSchoolId(school)
      fetchProfessors(school)
      fetchClasses(school)
      fetchStudents(school)
    }
    
    setLoading(false)
  }, [])

  // Efeito para aplicar filtros quando alunos, filtro de turma ou pesquisa mudam
  useEffect(() => {
    let currentStudents = [...students];

    // 1. Filtrar por NOME da turma selecionada
    if (selectedClassFilter) {
      console.log("\n[Filtro Turma] NOME da Turma Selecionada para Filtro:", selectedClassFilter, "(Tipo:", typeof selectedClassFilter, ")"); 
      currentStudents = currentStudents.filter(student => {
        // Comparação entre o NOME da turma do aluno e o NOME selecionado no filtro
        const studentClassNameStr = String(student.class_name || ''); // Garantir string e tratar undefined
        const selectedFilterNameStr = String(selectedClassFilter);
        const match = studentClassNameStr === selectedFilterNameStr;
        
        // Log para depuração
        if (students.indexOf(student) < 10 || !match) { 
            console.log(`  Comparando Aluno '${student.name}': Nome Turma Aluno='${studentClassNameStr}' vs Nome Filtro='${selectedFilterNameStr}' | Match? ${match}`);
        }
        return match;
      });
      console.log("[Filtro Turma] Alunos após filtro por nome:", currentStudents.length);
    }

    // 2. Filtrar por termo de pesquisa (nome ou email)
    if (searchQuery) {
      const lowerCaseQuery = searchQuery.toLowerCase();
      currentStudents = currentStudents.filter(student => 
        student.name.toLowerCase().includes(lowerCaseQuery) ||
        student.email.toLowerCase().includes(lowerCaseQuery)
      );
    }

    setFilteredStudents(currentStudents);

  }, [students, selectedClassFilter, searchQuery]); // Dependências do efeito

  const fetchProfessors = async (schoolId: string) => {
    try {
      setProfessorLoading(true)
      setError('')

      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/list-professors?school_id=${schoolId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`Erro ao buscar professores: ${response.status}`)
      }

      const data = await response.json()
      console.log('Professores:', data)
      
      // Verificar a estrutura da resposta e ajustar conforme necessário
      if (data && Array.isArray(data.data)) {
        setProfessors(data.data)
      } else if (data && Array.isArray(data)) {
        setProfessors(data)
      } else {
        console.error('Formato de resposta inesperado:', data)
        setProfessors([])
      }
    } catch (error) {
      console.error('Erro ao buscar professores:', error)
      setError('Não foi possível carregar a lista de professores')
    } finally {
      setProfessorLoading(false)
    }
  }
  
  // Função para buscar turmas
  const fetchClasses = async (schoolId: string) => {
    try {
      setClassLoading(true)
      setClassError('')

      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/list-classes?school_id=${schoolId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`Erro ao buscar turmas: ${response.status}`)
      }

      const data = await response.json()
      console.log('Dados brutos das turmas:', data)
      
      // Ajustar conforme a estrutura real da resposta da API
      if (data && Array.isArray(data.data)) {
        const mappedClasses = data.data.map((cls: any) => ({
          class_id: cls.id || cls.class_id || '',
          name: cls.name || 'Turma sem nome',
          professor_name: cls.professor_name || ''
        }))
        console.log('Turmas mapeadas:', mappedClasses)
        setClasses(mappedClasses)
      } else if (data && Array.isArray(data)) {
        const mappedClasses = data.map((cls: any) => ({
          class_id: cls.id || cls.class_id || '',
          name: cls.name || 'Turma sem nome',
          professor_name: cls.professor_name || ''
        }))
        console.log('Turmas mapeadas:', mappedClasses)
        setClasses(mappedClasses)
      } else {
        console.error('Formato de resposta inesperado para turmas:', data)
        setClasses([])
      }
    } catch (error) {
      console.error('Erro ao buscar turmas:', error)
      setClassError('Não foi possível carregar a lista de turmas')
    } finally {
      setClassLoading(false)
    }
  }
  
  // Função para buscar Alunos
  const fetchStudents = async (schoolId: string) => {
    try {
      setStudentLoading(true);
      setStudentError('');
      setStudents([]); // Limpa antes de buscar
      setFilteredStudents([]);

      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/list-students?school_id=${schoolId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          // Adicionar Authorization se necessário
        },
      });

      if (!response.ok) {
        throw new Error(`Erro ao buscar alunos: ${response.status}`);
      }

      const data = await response.json();
      console.log('Alunos:', data);

      // Ajustar conforme a estrutura real (parece ser data.data)
      if (data && Array.isArray(data.data)) {
        setStudents(data.data);
      } else if (data && Array.isArray(data)) {
        setStudents(data); // Fallback se a resposta for a lista direto
      } else {
        console.error('Formato de resposta inesperado para alunos:', data);
        setStudents([]);
      }
    } catch (error: any) {
      console.error('Erro ao buscar alunos:', error);
      setStudentError(error.message || 'Não foi possível carregar a lista de alunos');
    } finally {
      setStudentLoading(false);
    }
  };

  // Funções para modal de criação
  const handleOpenCreateClassModal = () => {
    // Resetar campos e resultados ao abrir
    setClassName('');
    setSelectedProfessorId('');
    setClassCreationResult(null);
    setIsCreateClassModalOpen(true);
  };

  const handleCloseCreateClassModal = () => {
    setIsCreateClassModalOpen(false);
  };

  // Função para criar uma nova turma (ajustada para fechar modal)
  const handleCreateClass = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validar os campos
    if (!className.trim()) {
      setClassCreationResult({
        success: false,
        message: 'Por favor, insira um nome para a turma'
      })
      return
    }
    
    try {
      setIsCreatingClass(true)
      setClassCreationResult(null)
      
      const payload: {
        name: string;
        school_id: string;
        professor_id?: string;
      } = {
        name: className,
        school_id: schoolId
      }
      
      // Adiciona professor_id apenas se estiver selecionado
      if (selectedProfessorId) {
        payload.professor_id = selectedProfessorId
      }
      
      console.log('Criando turma com os dados:', payload)
      
      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/class`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
      
      if (!response.ok) {
        throw new Error(`Erro ao criar turma: ${response.status}`)
      }
      
      const data = await response.json()
      console.log('Turma criada com sucesso:', data)
      
      setClassCreationResult({
        success: true,
        message: 'Turma criada com sucesso!'
      })
      
      // Limpar o formulário e fechar modal no sucesso
      handleCloseCreateClassModal();
      fetchClasses(schoolId); // Atualiza a lista

      // Opcional: Mostrar uma notificação de sucesso (toaster) fora do modal
      // alert('Turma criada com sucesso!'); 
      
    } catch (error) {
      console.error('Erro ao criar turma:', error)
      // Manter o erro dentro do modal
      setClassCreationResult({
        success: false,
        message: 'Ocorreu um erro ao criar a turma. Tente novamente.'
      })
    } finally {
      setIsCreatingClass(false)
    }
  }

  // Funções para exclusão DE TURMA (nome original)
  const handleOpenConfirmModal = (classItem: Class) => {
    console.log('[handleOpenConfirmModal] Abrindo modal para excluir turma:', classItem);
    setClassToDelete({ id: classItem.class_id, name: classItem.name });
    setDeleteError('');
    setIsConfirmModalOpen(true);
  };

  const handleCloseConfirmModal = () => {
    setIsConfirmModalOpen(false);
    // Atraso para limpar classToDelete para a animação do modal (opcional)
    setTimeout(() => setClassToDelete(null), 300);
  };

  const handleConfirmDelete = async () => {
    // VERIFICAÇÃO ADICIONADA para ID da turma
    if (!classToDelete || !classToDelete.id) {
      console.error('[handleConfirmDelete] Erro: Tentativa de excluir turma sem ID válido.', classToDelete);
      setDeleteError('Não foi possível excluir: ID da turma inválido.');
      return; 
    }

    console.log(`[handleConfirmDelete] Iniciando exclusão para ID: ${classToDelete.id}`); // Log antes do fetch

    setIsDeletingClass(true);
    setDeleteError('');

    try {
      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/class/${classToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        let errorMsg = `Erro ao excluir turma: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.message || errorData.detail || errorMsg;
        } catch (e) { /* Ignorar */ }
        throw new Error(errorMsg);
      }

      console.log('[handleConfirmDelete] Turma excluída com sucesso:', classToDelete.id);
      handleCloseConfirmModal();
      fetchClasses(schoolId);

    } catch (error: any) {
      console.error('[handleConfirmDelete] Erro durante a exclusão:', error);
      setDeleteError(error.message || 'Ocorreu um erro ao excluir a turma.');
    } finally {
      setIsDeletingClass(false);
    }
  };

  // Funções para exclusão de PROFESSOR
  const handleOpenConfirmDeleteProfessorModal = (professor: Professor) => {
    console.log('[handleOpenConfirmDeleteProfessorModal] Abrindo modal para excluir professor:', professor); // Log adicional
    setProfessorToDelete({ id: professor.professor_id, name: professor.name }); 
    setDeleteProfessorError(''); 
    setIsConfirmDeleteProfessorModalOpen(true);
  };

  const handleCloseConfirmDeleteProfessorModal = () => {
    setIsConfirmDeleteProfessorModalOpen(false);
    setTimeout(() => setProfessorToDelete(null), 300); // Atraso opcional
  };

  const handleConfirmDeleteProfessor = async () => {
    if (!professorToDelete) return;

    setIsDeletingProfessor(true);
    setDeleteProfessorError('');

    try {
      // Atenção: A rota da API parece ser /manager/professors/{professor_id}
      // Ajuste se a estrutura for diferente (ex: /manager/professor/{id})
      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/professors/${professorToDelete.id}`, {
        method: 'DELETE',
        headers: {
          // Adicionar headers necessários (Authorization?)
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        let errorMsg = `Erro ao excluir professor: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.message || errorData.detail || errorMsg;
        } catch (e) { /* Ignorar */ }
        throw new Error(errorMsg);
      }

      console.log('Professor excluído com sucesso:', professorToDelete.id);
      handleCloseConfirmDeleteProfessorModal();
      fetchProfessors(schoolId); // Atualiza a lista de professores
      fetchClasses(schoolId); // Atualiza turmas (professor pode ter sido removido de alguma)

    } catch (error: any) {
      console.error('Erro ao excluir professor:', error);
      setDeleteProfessorError(error.message || 'Ocorreu um erro ao excluir o professor.');
    } finally {
      setIsDeletingProfessor(false);
    }
  };

  // Funções para exclusão de ALUNO
  const handleOpenConfirmDeleteStudentModal = (student: Student) => {
    setStudentToDelete({ id: student.student_id, name: student.name });
    setDeleteStudentError(''); // Limpa erro anterior
    setIsConfirmDeleteStudentModalOpen(true);
  };

  const handleCloseConfirmDeleteStudentModal = () => {
    setIsConfirmDeleteStudentModalOpen(false);
    setTimeout(() => setStudentToDelete(null), 300); // Atraso opcional
  };

  const handleConfirmDeleteStudent = async () => {
    if (!studentToDelete) return;

    setIsDeletingStudent(true);
    setDeleteStudentError('');

    try {
      // Tentativa com rota no singular: /manager/student/{student_id}
      const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/student/${studentToDelete.id}`, {
        method: 'DELETE',
        headers: {
          // Adicionar headers necessários (Authorization?)
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        let errorMsg = `Erro ao excluir aluno: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.message || errorData.detail || errorMsg;
        } catch (e) { /* Ignorar */ }
        throw new Error(errorMsg);
      }

      console.log('Aluno excluído com sucesso:', studentToDelete.id);
      handleCloseConfirmDeleteStudentModal();
      fetchStudents(schoolId); // Atualiza a lista de alunos

    } catch (error: any) {
      console.error('Erro ao excluir aluno:', error);
      setDeleteStudentError(error.message || 'Ocorreu um erro ao excluir o aluno.');
    } finally {
      setIsDeletingStudent(false);
    }
  };

  // Funções para Bulk Register Modal
  const handleOpenBulkRegisterModal = () => {
    setSelectedFile(null);         // Limpa arquivo selecionado
    setTargetClassId('');         // Limpa turma selecionada
    setBulkRegisterResult(null); // Limpa resultado anterior
    setIsBulkRegisterModalOpen(true);
  };

  const handleCloseBulkRegisterModal = () => {
    setIsBulkRegisterModalOpen(false);
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
      setBulkRegisterResult(null); // Limpa resultado ao mudar arquivo
    } else {
      setSelectedFile(null);
    }
  };
  
  // Drag and Drop Handlers (opcional mas melhora UX)
  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault(); // Necessário para permitir o drop
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.dataTransfer.files && event.dataTransfer.files[0]) {
       // Validar tipo de arquivo se necessário
       const file = event.dataTransfer.files[0];
       if (file.type === 'text/csv' || 
           file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || 
           file.type === 'application/vnd.ms-excel') {
            setSelectedFile(file);
            setBulkRegisterResult(null); 
       } else {
            setSelectedFile(null);
            setBulkRegisterResult({success: false, message: 'Tipo de arquivo inválido. Use CSV ou XLSX.'});
       }
    } else {
        setSelectedFile(null);
    }
  };

  // Função de Submit do Bulk Register
  const handleBulkRegisterSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!selectedFile) {
      setBulkRegisterResult({ success: false, message: 'Por favor, selecione um arquivo CSV ou XLSX.' });
      return;
    }
    if (!targetClassId) {
      // Mesmo que seja professor, a API parece exigir class_id no query param
      setBulkRegisterResult({ success: false, message: 'Por favor, selecione uma turma de destino.' });
      return;
    }

    setIsSubmittingBulk(true);
    setBulkRegisterResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile); // A API espera o arquivo com a chave 'file'

    // Construir URL com query parameters
    const apiUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/bulk-register?school_id=${schoolId}&class_id=${targetClassId}`;
    console.log('Enviando para:', apiUrl);
    console.log('FormData contém arquivo:', formData.has('file'));

    try {
      const response = await authFetch(apiUrl, {
        method: 'POST',
        headers: {
          // NÃO definir 'Content-Type', o browser faz isso para FormData
          // Adicionar Authorization se necessário
        },
        body: formData,
      });

      if (!response.ok) {
        let errorMsg = `Erro no registro em massa: ${response.status}`;
        try {
          const errorData = await response.json();
          // Tenta pegar mensagens de erro comuns da API
          if (errorData.detail && typeof errorData.detail === 'string') {
              errorMsg = errorData.detail;
          } else if (errorData.message) {
              errorMsg = errorData.message;
          } else if (Array.isArray(errorData.detail)) { // FastAPI validation errors
              errorMsg = errorData.detail.map((err: any) => `${err.loc?.join('.')} - ${err.msg}`).join('; ');
          }
        } catch (e) { /* Ignorar se não for JSON */ }
        throw new Error(errorMsg);
      }

      const resultData = await response.json();
      console.log('Resultado Bulk Register:', resultData);
      setBulkRegisterResult({ success: true, message: resultData.message || 'Usuários registrados com sucesso!' });
      
      // Limpar e fechar modal após sucesso
      handleCloseBulkRegisterModal();
      
      // Atualizar listas relevantes
      fetchProfessors(schoolId);
      fetchStudents(schoolId);
      // fetchClasses(schoolId); // Descomentar se o registro afetar dados das turmas

    } catch (error: any) {
      console.error('Erro no bulk register:', error);
      setBulkRegisterResult({ success: false, message: error.message || 'Ocorreu um erro inesperado.' });
    } finally {
      setIsSubmittingBulk(false);
    }
  };

  if (loading) {
    return (
      <Layout role="professor" background="#f5f5f5">
        <div className={styles.loadingContainer || ''}>
          <div key="initial-loading">Carregando...</div>
        </div>
      </Layout>
    )
  }

  return (
    <div>
      <div className={styles.dashboardContainer}>
        <h1 className={styles.dashboardTitle}>Dashboard Admin Interno</h1>
        <p className={styles.welcomeText}>Bem-vindo, {userName}!</p>
        
        <div className={styles.cardsContainer}>
          {/* Card de Professores */}
          <div className={styles.card}>
            <div className={`${styles.cardHeader} ${styles.cardHeaderWithButton}`}>
              <h2 className={styles.cardTitle}>
                <UserCog className={styles.cardIcon} />
                Professores
              </h2>
              <Button
                onClick={handleOpenBulkRegisterModal}
                className={styles.createButtonHeader}
                variant="contained"
                size="small"
                startIcon={<UploadCloud size={16}/>}
              >
                Registrar em Massa
              </Button>
            </div>

            <div className={styles.cardContent}>
              {professorLoading ? (
                <div key="loading" className={styles.loadingSpinner}>Carregando professores...</div>
              ) : error ? (
                <div key="error" className={styles.errorMessage}>{error}</div>
              ) : professors.length === 0 ? (
                <div key="empty" className={styles.emptyState}>Nenhum professor encontrado</div>
              ) : (
                <div key="professors-list" className={styles.professorsList}>
                  {professors.map((professor, index) => (
                    <div 
                      key={professor.professor_id || `professor-${index}`} 
                      className={styles.professorItem}
                    >
                      <div className={styles.professorMainInfo}>
                        <div className={styles.professorAvatar}>
                          <UserCog size={24} />
                        </div>
                        <div className={styles.professorInfo}>
                          <h3 className={styles.professorName}>{professor.name}</h3>
                          <div className={styles.professorContact}>
                            <div key={`email-${professor.professor_id || index}`} className={styles.contactItem}>
                              <Mail size={14} />
                              <span>{professor.email || 'Sem e-mail'}</span>
                            </div>
                            {professor.phone && (
                              <div key={`phone-${professor.professor_id || index}`} className={styles.contactItem}>
                                <Phone size={14} />
                                <span>{professor.phone}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className={styles.professorActions}>
                        <button 
                          onClick={() => handleOpenConfirmDeleteProfessorModal(professor)}
                          className={styles.deleteButton}
                          title="Excluir Professor"
                          disabled={isDeletingProfessor}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          {/* Card Único de Turmas (Listagem + Botão Criar) */}
          <div className={styles.card}>
            <div className={`${styles.cardHeader} ${styles.cardHeaderWithButton}`}>
              <h2 className={styles.cardTitle}>
                <Users className={styles.cardIcon} />
                Turmas
              </h2>
              <Button
                onClick={handleOpenCreateClassModal}
                className={styles.createButtonHeader}
                variant="contained"
                size="small"
                startIcon={<Plus size={16}/>}
              >
                Criar Turma
              </Button>
            </div>

            <div className={styles.cardContent}>
              {classLoading ? (
                <div key="loading-classes" className={styles.loadingSpinner}>Carregando turmas...</div>
              ) : classError ? (
                <div key="error-classes" className={styles.errorMessage}>{classError}</div>
              ) : classes.length === 0 ? (
                <div key="empty-classes" className={styles.emptyState}>Nenhuma turma encontrada</div>
              ) : (
                <div key="classes-list" className={styles.classesList}>
                  {classes.map((classItem, index) => (
                    <div 
                      key={classItem.class_id || `class-${index}`} 
                      className={styles.classItem}
                    >
                      <div className={styles.classInfo}>
                        <h3 className={styles.className}>{classItem.name}</h3>
                        {classItem.professor_name && (
                          <p className={styles.classProfessor}>
                            Professor: {classItem.professor_name}
                          </p>
                        )}
                      </div>
                      <div className={styles.classActions}>
                        <button 
                          onClick={() => handleOpenConfirmModal(classItem)}
                          className={styles.deleteButton}
                          title="Excluir Turma"
                          disabled={isDeletingClass}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          {/* Card de Alunos com Filtros */}
          <div className={styles.card}>
            <div className={`${styles.cardHeader} ${styles.cardHeaderWithButton}`}>
              <h2 className={styles.cardTitle}>
                <Users className={styles.cardIcon} />
                Alunos
              </h2>
              <Button
                onClick={handleOpenBulkRegisterModal}
                className={styles.createButtonHeader}
                variant="contained"
                size="small"
                startIcon={<UploadCloud size={16}/>}
              >
                Registrar em Massa
              </Button>
            </div>

            <div className={styles.cardContent}>
              {/* Filtros */} 
              <div className={styles.filtersContainer}>
                {/* Filtro por Turma */} 
                <div className={styles.filterGroup}>
                  <label htmlFor="classFilterSelect" className={styles.filterLabel}>Filtrar por Turma:</label>
                  <select
                    id="classFilterSelect"
                    value={selectedClassFilter}
                    onChange={(e) => setSelectedClassFilter(e.target.value)}
                    className={styles.filterSelect}
                    disabled={classLoading}
                  >
                    <option key="all-classes-filter-option" value="">Todas as Turmas</option>
                    {classes.map((classItem, index) => {
                      const optionValue = classItem.name; 
                      // Key usa class_id
                      const optionKey = classItem.class_id ? String(classItem.class_id) : `class-filter-option-${index}`;
                      return (
                        <option key={optionKey} value={optionValue}>
                          {classItem.name}
                        </option>
                      );
                    })}
                  </select>
                </div>

                {/* Filtro por Pesquisa */} 
                <div className={styles.filterGroup}> 
                  <label htmlFor="searchStudentInput" className={styles.filterLabel}>Pesquisar:</label>
                  <div className={styles.searchInputContainer}>
                    <Search size={18} className={styles.searchIcon} />
                    <input
                      id="searchStudentInput"
                      type="text"
                      placeholder="Nome ou E-mail do Aluno"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className={styles.filterInput}
                    />
                  </div>
                </div>
              </div>

              {/* Lista de Alunos */} 
              <div className={styles.studentsListContainer}>
                {studentLoading ? (
                  <div key="loading-students" className={styles.loadingSpinner}>Carregando alunos...</div>
                ) : studentError ? (
                  <div key="error-students" className={styles.errorMessage}>{studentError}</div>
                ) : filteredStudents.length === 0 ? (
                  <div key="empty-students" className={styles.emptyState}>
                    {searchQuery || selectedClassFilter ? 'Nenhum aluno encontrado com os filtros aplicados' : 'Nenhum aluno encontrado'}
                  </div>
                ) : (
                  <div key="students-list" className={styles.studentsList}>
                    {filteredStudents.map((student, index) => (
                      <div 
                        key={student.student_id || `student-${index}`}
                        className={styles.studentItem}
                      >
                        <div className={styles.studentInfo}>
                          <h3 className={styles.studentName}>{student.name}</h3>
                          <p className={styles.studentEmail}>{student.email}</p>
                          <p className={styles.studentClass}>Turma: {student.class_name || 'Não definida'}</p>
                        </div>
                        <div className={styles.studentActions}>
                          <button 
                            onClick={() => handleOpenConfirmDeleteStudentModal(student)}
                            className={styles.deleteButton}
                            title="Excluir Aluno"
                            disabled={isDeletingStudent}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          
        </div>
      </div>

      {/* Modal de Criação de Turma */} 
      <Modal
        open={isCreateClassModalOpen}
        onClose={(_, reason) => {
          if (reason !== 'backdropClick' || !isCreatingClass) {
            handleCloseCreateClassModal();
          }
        }}
        aria-labelledby="create-class-modal-title"
        className={styles.modalBackdrop}
      >
        <Box className={styles.modalContent} component="form" onSubmit={handleCreateClass}>
          <Typography id="create-class-modal-title" className={styles.modalTitle}>
            Criar Nova Turma
          </Typography>

          {/* Formulário movido para cá */}
          <div className={styles.formGroup}>
            <label htmlFor="classNameModal" className={styles.formLabel}>
              Nome da Turma
            </label>
            <input
              id="classNameModal" // ID diferente para evitar conflito
              type="text"
              value={className}
              onChange={(e) => setClassName(e.target.value)}
              className={styles.formInput}
              placeholder="Digite o nome da turma"
              disabled={isCreatingClass}
              required // Adiciona validação HTML básica
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="professorSelectModal" className={styles.formLabel}>
              Professor Responsável (Opcional)
            </label>
            <select
              id="professorSelectModal" // ID diferente
              value={selectedProfessorId}
              onChange={(e) => setSelectedProfessorId(e.target.value)}
              className={styles.formSelect}
              disabled={isCreatingClass || professorLoading || professors.length === 0}
            >
              <option key="default-professor-option-modal" value="">Selecione um professor (opcional)</option>
              {professors.map((professor, index) => (
                <option key={professor.professor_id ? String(professor.professor_id) : `professor-option-modal-${index}`} value={professor.professor_id}>
                  {professor.name}
                </option>
              ))}
            </select>
          </div>

          {classCreationResult && !classCreationResult.success && ( // Mostrar erro apenas se houver falha
            <div 
              key="create-result-message"
              className={`${styles.resultMessage} ${styles.errorMessage}`}
            >
              <AlertCircle key="error-icon-modal" size={18} className={styles.resultIcon} />
              <span>{classCreationResult.message}</span>
            </div>
          )}
          
          {/* Ações do Modal de Criação */} 
          <div className={styles.modalActions}>
            <Button 
              type="submit" 
              className={styles.createButtonModal} // Estilo específico para o botão criar no modal
              disabled={isCreatingClass}
              variant="contained"
            >
              {isCreatingClass ? 'Criando...' : 'Criar Turma'}
            </Button>
             <Button
              onClick={handleCloseCreateClassModal}
              className={styles.cancelButton} // Reutiliza estilo do botão cancelar
              disabled={isCreatingClass}
            >
              Cancelar
            </Button>
          </div>
        </Box>
      </Modal>

      {/* Modal de confirmação de exclusão */}
      <Modal
        open={isConfirmModalOpen}
        onClose={(_, reason) => {
          if (reason !== 'backdropClick' || !isDeletingClass) {
            handleCloseConfirmModal();
          }
        }}
        aria-labelledby="modal-title"
        aria-describedby="modal-description"
        className={styles.modalBackdrop}
      >
        <Box className={styles.modalContent}>
          <Typography id="modal-title" className={styles.modalTitle}>
            Confirmar Exclusão
          </Typography>
          <Typography id="modal-description" className={styles.modalDescription}>
            Tem certeza de que deseja excluir a turma "<strong>{classToDelete?.name}</strong>"?<br />
            Esta ação não pode ser desfeita.
          </Typography>
          
          {deleteError && (
            <div key="delete-error-msg" className={styles.modalError}>
              <AlertCircle size={16} />
              <span>{deleteError}</span>
            </div>
          )}
          
          <div className={styles.modalActions}>
            <Button
              onClick={handleConfirmDelete}
              className={styles.confirmButton}
              disabled={isDeletingClass}
            >
              {isDeletingClass ? 'Excluindo...' : 'Excluir'}
            </Button>
            <Button
              onClick={handleCloseConfirmModal}
              className={styles.cancelButton}
              disabled={isDeletingClass}
            >
              Cancelar
            </Button>
          </div>
        </Box>
      </Modal>

      {/* Modal de confirmação de exclusão de professor */}
      <Modal
        open={isConfirmDeleteProfessorModalOpen}
        onClose={(_, reason) => {
          if (reason !== 'backdropClick' || !isDeletingProfessor) {
            handleCloseConfirmDeleteProfessorModal();
          }
        }}
        aria-labelledby="modal-title-professor"
        aria-describedby="modal-description-professor"
        className={styles.modalBackdrop}
      >
        <Box className={styles.modalContent}>
          <Typography id="modal-title-professor" className={styles.modalTitle}>
            Confirmar Exclusão
          </Typography>
          <Typography id="modal-description-professor" className={styles.modalDescription}>
            Tem certeza de que deseja excluir o professor "<strong>{professorToDelete?.name}</strong>"?<br />
            Esta ação não pode ser desfeita.
          </Typography>
          
          {deleteProfessorError && (
            <div key="delete-professor-error-msg" className={styles.modalError}>
              <AlertCircle size={16} />
              <span>{deleteProfessorError}</span>
            </div>
          )}
          
          <div className={styles.modalActions}>
            <Button
              onClick={handleConfirmDeleteProfessor}
              className={styles.confirmButton}
              disabled={isDeletingProfessor}
            >
              {isDeletingProfessor ? 'Excluindo...' : 'Excluir'}
            </Button>
            <Button
              onClick={handleCloseConfirmDeleteProfessorModal}
              className={styles.cancelButton}
              disabled={isDeletingProfessor}
            >
              Cancelar
            </Button>
          </div>
        </Box>
      </Modal>

      {/* Modal de confirmação de exclusão de aluno */}
      <Modal
        open={isConfirmDeleteStudentModalOpen}
        onClose={(_, reason) => {
          if (reason !== 'backdropClick' || !isDeletingStudent) {
            handleCloseConfirmDeleteStudentModal();
          }
        }}
        aria-labelledby="modal-title-student"
        aria-describedby="modal-description-student"
        className={styles.modalBackdrop}
      >
        <Box className={styles.modalContent}>
          <Typography id="modal-title-student" className={styles.modalTitle}>
            Confirmar Exclusão
          </Typography>
          <Typography id="modal-description-student" className={styles.modalDescription}>
            Tem certeza de que deseja excluir o aluno "<strong>{studentToDelete?.name}</strong>"?<br />
            Esta ação não pode ser desfeita.
          </Typography>
          
          {deleteStudentError && (
            <div key="delete-student-error-msg" className={styles.modalError}>
              <AlertCircle size={16} />
              <span>{deleteStudentError}</span>
            </div>
          )}
          
          <div className={styles.modalActions}>
            <Button
              onClick={handleConfirmDeleteStudent}
              className={styles.confirmButton}
              disabled={isDeletingStudent}
            >
              {isDeletingStudent ? 'Excluindo...' : 'Excluir'}
            </Button>
            <Button
              onClick={handleCloseConfirmDeleteStudentModal}
              className={styles.cancelButton}
              disabled={isDeletingStudent}
            >
              Cancelar
            </Button>
          </div>
        </Box>
      </Modal>

      {/* Modal de Bulk Register */}
      <Modal
        open={isBulkRegisterModalOpen}
        onClose={(_, reason) => {
          if (reason !== 'backdropClick' || !isSubmittingBulk) {
            handleCloseBulkRegisterModal();
          }
        }}
        aria-labelledby="modal-title-bulk-register"
        aria-describedby="modal-description-bulk-register"
        className={styles.modalBackdrop}
      >
        <Box 
          className={styles.modalContent} 
          component="form" 
          id="bulk-register-form"
          onSubmit={handleBulkRegisterSubmit}
        >
          <Typography id="modal-title-bulk-register" className={styles.modalTitle}>
            Registrar Usuários em Massa
          </Typography>
          <Typography id="modal-description-bulk-register" className={styles.modalDescription}>
            Arraste ou selecione um arquivo CSV ou XLSX com as colunas: 
            `email`, `name`, `role` (`student` ou `professor`). 
            Selecione a turma para vincular os novos usuários.
          </Typography>
          
          <div 
            className={styles.dropZone}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => document.getElementById('fileInputBulk')?.click()}
          >
             <input
              id="fileInputBulk"
              type="file"
              accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
              onChange={handleFileChange}
              className={styles.fileInputHidden}
              disabled={isSubmittingBulk}
            />
            {selectedFile ? (
                <p>Arquivo selecionado: {selectedFile.name}</p>
            ) : (
                <> 
                  <UploadCloud size={32} style={{ marginBottom: '0.5rem', color: '#718096'}}/>
                  <p>Arraste e solte o arquivo aqui ou clique para selecionar</p>
                </>
            )}
          </div>
          
          {bulkRegisterResult && (
            <div 
              key="bulk-register-result-message" 
              className={`${styles.resultMessage} ${bulkRegisterResult.success ? styles.successMessage : styles.errorMessage}`} 
              style={{ marginTop: '1rem' }}
            >
               {bulkRegisterResult.success ? <Check size={18}/> : <AlertCircle size={18}/>}
               <span>{bulkRegisterResult.message}</span>
            </div>
           )}
          
          <div className={styles.formGroup} style={{ marginTop: '1.5rem' }}>
            <label htmlFor="targetClassSelectBulk" className={styles.formLabel}>
              Vincular à Turma:
            </label>
            <select
              id="targetClassSelectBulk"
              value={targetClassId}
              onChange={(e) => {
                console.log('Turma selecionada:', e.target.value)
                setTargetClassId(e.target.value)
              }}
              className={styles.formSelect}
              disabled={isSubmittingBulk || classLoading}
              required
            >
              <option key="default-class-option-bulk" value="">Selecione a turma de destino</option>
              {classes.map((classItem, index) => {
                console.log('Opção de turma:', classItem)
                return (
                  <option 
                    key={classItem.class_id || `bulk-class-opt-${index}`} 
                    value={classItem.class_id}
                  > 
                    {classItem.name}
                  </option>
                )
              })}
            </select>
          </div>

          <div className={styles.modalActions}>
            <Button 
              type="submit" 
              form="bulk-register-form"
              className={styles.createButtonModal}
              disabled={isSubmittingBulk || !selectedFile || !targetClassId}
              variant="contained"
            >
              {isSubmittingBulk ? 'Registrando...' : 'Registrar Usuários'}
            </Button>
             <Button
              onClick={handleCloseBulkRegisterModal}
              className={styles.cancelButton}
              disabled={isSubmittingBulk}
            >
              Cancelar
            </Button>
          </div>
        </Box>
      </Modal>
    </div>
  )
}