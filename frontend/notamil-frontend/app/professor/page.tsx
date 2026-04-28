"use client"

import { useState, useEffect } from "react"
import { ChevronDown, FileText, X, PenLine } from "lucide-react"
import styles from "./professor.module.css"
import Layout from "../dashboard/components/Layout"
import RouteGuard from "../components/RouteGuard"
import ProfessorDataFetcher from "../components/professorDataFetcher"
import CorrecaoProfessorModal from "../components/CorrecaoProfessorModal"
import { authFetch } from "@/services/authFetch"

// Interfaces
interface Student {
  id?: string
  student_user_id?: string
  name: string
  grade?: number
  average_grade?: number
}

interface CompetencyData {
  id: number | string
  name: string
  value: number
  color: string
  competency?: string
  average_grade?: string | number
}

interface ClassData {
  id: string
  name: string
  average_grade: number
  students: Student[]
  competencies: CompetencyData[]
}

interface ClassInfo {
  id: string
  name: string
  average_grade?: string | number
}

interface EssayData {
  overall_grade: number;
  theme: string;
  competencies: {
    [competencyName: string]: {
      grade: number;
      detailed_analysis: string;
      justification: string;
    };
  };
}

interface StudentEssays {
  total_essays: number;
  average_grade: number;
  competency_averages: {
    [competencyName: string]: number;
  };
  essays: {
    [essayId: string]: EssayData;
  };
}

export default function TeacherDashboardPage() {
  const [selectedClass, setSelectedClass] = useState<ClassData | null>(null)
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [showAllStudents, setShowAllStudents] = useState(false)
  const [apiClasses, setApiClasses] = useState<ClassInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [initialLoading, setInitialLoading] = useState(true) // Para controlar o carregamento inicial
  const [isEssayModalOpen, setIsEssayModalOpen] = useState(false)
  const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false)
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null)
  const [studentEssays, setStudentEssays] = useState<StudentEssays | null>(null)
  const [essaysLoading, setEssaysLoading] = useState(false)
  const [selectedEssayId, setSelectedEssayId] = useState<string>("")
  const [dataLoadedOnce, setDataLoadedOnce] = useState(false) // Flag para saber se já carregamos os dados uma vez
  
  // Estados para a criação de temas
  const [isThemeModalOpen, setIsThemeModalOpen] = useState(false)
  const [themeTitle, setThemeTitle] = useState("")
  const [themeDescription, setThemeDescription] = useState("")
  const [selectedClasses, setSelectedClasses] = useState<{[id: string]: boolean}>({})
  const [isSubmittingTheme, setIsSubmittingTheme] = useState(false)
  const [themeResult, setThemeResult] = useState<{success: boolean, message: string} | null>(null)

  // Log de depuração para selectedClass
  useEffect(() => {
    if (selectedClass) {
      console.log("DEBUG - selectedClass:", selectedClass);
      console.log("average_grade:", selectedClass.average_grade, "tipo:", typeof selectedClass.average_grade);
    }
  }, [selectedClass]);

  // Handler para receber as turmas do ProfessorDataFetcher
  const handleClassesLoaded = (loadedClasses: ClassInfo[]) => {
    console.log("Turmas carregadas:", loadedClasses);
    
    // Atualiza o estado com as turmas da API
    setApiClasses(loadedClasses);
    
    // Se houver turmas, seleciona a primeira por padrão
    if (loadedClasses.length > 0) {
      const firstClass = loadedClasses[0];
      console.log("DEBUG - firstClass average_grade (original):", firstClass.average_grade, "tipo:", typeof firstClass.average_grade);
      
      const parsedAverage = parseInt(String(firstClass.average_grade)) || 0;
      console.log("DEBUG - parsedAverage:", parsedAverage, "tipo:", typeof parsedAverage);
      
      // Cria uma estrutura inicial para a classe selecionada
      const initialClass: ClassData = {
        id: firstClass.id,
        name: firstClass.name,
        average_grade: parsedAverage,
        students: [],
        competencies: []
      };
      
      console.log("DEBUG - initialClass:", initialClass);
      
      // Define a classe selecionada
      setSelectedClass(initialClass);
      
      // Define o ID da turma selecionada para futuras chamadas de API
      setSelectedClassId(firstClass.id);
      console.log("Nova turma selecionada:", firstClass)
    } else {
      // Se não houver turmas, encerra o carregamento
      setIsLoading(false);
      setInitialLoading(false);
    }
  };

  // Handler para receber dados específicos de uma turma
  const handleClassDataLoaded = (classData: any) => {
    console.log("Dados específicos da turma recebidos:", classData);
    
    if (classData && selectedClass) {
      // Processamento dos dados de alunos
      let mappedStudents: Student[] = [];
      
      // Usamos a média que vem diretamente do backend
      let classAverage = selectedClass.average_grade;
      
      // Se a API retornar a média da turma, usamos esse valor
      if (classData.average_grade) {
        classAverage = parseInt(String(classData.average_grade)) || classAverage;
      }
      
      if (classData.students && classData.students.data) {
        const studentsFromApi = classData.students.data || [];
        
        mappedStudents = studentsFromApi.map((student: any) => ({
          id: student.student_user_id,
          student_user_id: student.student_user_id,
          name: student.name,
          grade: student.average_grade,
          average_grade: student.average_grade
        }));
        
        console.log("Alunos processados:", mappedStudents);
        
        // Removida a lógica de cálculo da média da turma
      }
      
      // Processamento dos dados de competências
      let mappedCompetencies: CompetencyData[] = [];
      
      if (classData.competencies && classData.competencies.data) {
        const competenciesFromApi = classData.competencies.data || [];
        
        // Definir cores para as competências
        const competencyColors = {
          "Domínio da Norma Culta": "#4361EE",
          "Compreensão do Tema": "#3ADAA8",
          "Seleção e Organização das Informações": "#0096FF",
          "Conhecimento dos Mecanismos Linguísticos": "#C5F364",
          "Proposta de Intervenção": "#A0AEC0"
        };
        
        mappedCompetencies = competenciesFromApi.map((comp: any, index: number) => ({
          id: index + 1,
          name: comp.competency,
          competency: comp.competency,
          value: parseInt(String(comp.average_grade)),
          average_grade: comp.average_grade,
          color: competencyColors[comp.competency as keyof typeof competencyColors] || `hsl(${index * 50}, 70%, 50%)`
        }));
        
        console.log("Competências processadas:", mappedCompetencies);
      }
      
      // Cria uma cópia do objeto atual com os novos dados
      const updatedClass = {
        ...selectedClass,
        // Atualiza alunos e competências com os dados da API
        students: mappedStudents,
        competencies: mappedCompetencies,
        // Usa a média que vem do backend
        average_grade: classAverage
      };
      
      setSelectedClass(updatedClass);
    }
    
    // Marca o carregamento como concluído
    setIsLoading(false);
    setInitialLoading(false);
    setDataLoadedOnce(true);
  };

  // Função para buscar redações de um aluno específico
  // Função para buscar redações de um aluno específico
  const fetchStudentEssays = async (studentId: string): Promise<void> => {
    try {
      console.log("📡 Fazendo requisição para:", `${process.env.NEXT_PUBLIC_API_BASE_URL}/dashboard/user?user_id=${studentId}`);
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/dashboard/user?user_id=${studentId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });
      
      if (!response.ok) {
        throw new Error("Erro ao buscar redações do aluno");
      }
      
      const data = await response.json();
      setStudentEssays(data);
      
      // Verifica se há redações
      if (!data.essays || Object.keys(data.essays).length === 0) {
        alert("Este aluno ainda não tem redações enviadas");
        setIsEssayModalOpen(false); // Fecha a modal se não houver redações
      }
    } catch (error) {
      console.error("Erro ao buscar redações do aluno:", error);
      alert("Erro ao buscar redações do aluno. Tente novamente.");
      setIsEssayModalOpen(false); // Fecha a modal em caso de erro
    } finally {
      setEssaysLoading(false); // Desativa o loading em qualquer caso
    }
  };

  // Função para lidar com o clique no botão de relatório
  const handleReportClick = (student: Student) => {
    setSelectedStudent(student);
    
    // Verifica se temos o ID do aluno
    if (student && (student.id || student.student_user_id)) {
      // Ativa o loading da modal
      setEssaysLoading(true);
      // Abre a modal imediatamente, mostrando o loading interno
      setIsEssayModalOpen(true);
      
      // Busca os dados das redações
      fetchStudentEssays(student.id || student.student_user_id || "");
    } else {
      alert("ID do aluno não encontrado");
    }
  };

  // Função para quando selecionar uma redação na modal
  const handleEssaySelect = (essayId: string) => {
    // Define o ID da redação selecionada
    setSelectedEssayId(essayId);
    
    // Fecha a modal de seleção de redações
    setIsEssayModalOpen(false);
    
    // Abre a modal de correção
    setIsCorrectionModalOpen(true);
  };

  // Função para determinar a cor da nota
  const getGradeColor = (grade: number) => {
    if (grade >= 800) return "#3ADAA8" // Verde
    if (grade >= 600) return "#F59E0B" // Amarelo
    return "#EF4444" // Vermelho
  }

  // Função para formatar a média para exibição
  const formatAverage = (average: any): string => {
    if (average === undefined || average === null) return "0";
    if (typeof average === 'number') return String(average);
    if (typeof average === 'string') return average;
    return String(parseInt(String(average)) || 0);
  }

  // Função para lidar com a seleção de turmas na modal de criação de tema
  const handleClassSelection = (classId: string) => {
    setSelectedClasses(prev => ({
      ...prev,
      [classId]: !prev[classId]
    }));
  };

  // Função para lidar com o envio do tema para a API
  const handleSubmitTheme = async () => {
    try {
      setIsSubmittingTheme(true);
      setThemeResult(null);
      
      // Obter os IDs das turmas selecionadas
      const selectedClassIds = Object.entries(selectedClasses)
        .filter(([_, isSelected]) => isSelected)
        .map(([classId, _]) => classId);
      
      if (selectedClassIds.length === 0) {
        setThemeResult({
          success: false,
          message: "Selecione pelo menos uma turma para aplicar o tema."
        });
        setIsSubmittingTheme(false);
        return;
      }
      
      if (!themeTitle.trim()) {
        setThemeResult({
          success: false,
          message: "O título do tema é obrigatório."
        });
        setIsSubmittingTheme(false);
        return;
      }
      
      // Para cada turma selecionada, enviar uma requisição para a API
      const results = await Promise.all(
        selectedClassIds.map(async (classId) => {
          const response = await authFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/manager/theme`, {
            method: "POST",
            body: JSON.stringify({
              name: themeTitle,
              description: themeDescription,
              class_id: classId
            }),
          });
          
          const result = await response.json();
          return {
            classId,
            success: response.ok,
            data: result
          };
        })
      );
      
      // Verificar se todas as requisições foram bem-sucedidas
      const allSuccessful = results.every(result => result.success);
      
      if (allSuccessful) {
        setThemeResult({
          success: true,
          message: `Tema aplicado com sucesso em ${results.length} turma(s).`
        });
        // Limpar os campos após o sucesso
        setThemeTitle("");
        setThemeDescription("");
        setSelectedClasses({});
        
        // Fechar a modal após 2 segundos
        setTimeout(() => {
          setIsThemeModalOpen(false);
          setThemeResult(null);
        }, 2000);
      } else {
        const failedClasses = results.filter(r => !r.success).length;
        setThemeResult({
          success: false,
          message: `Erro ao aplicar o tema em ${failedClasses} turma(s). Por favor, tente novamente.`
        });
      }
    } catch (error) {
      console.error("Erro ao enviar tema:", error);
      setThemeResult({
        success: false,
        message: "Ocorreu um erro ao enviar o tema. Por favor, tente novamente."
      });
    } finally {
      setIsSubmittingTheme(false);
    }
  };

  // Modificando a lógica para lidar com a troca de turma
  const handleClassChange = (classItem: ClassInfo) => {
    // Primeiro fechamos o dropdown
    setIsDropdownOpen(false);
    
    // Verifica se já é a mesma turma
    if (classItem.id === selectedClassId) {
      return; // Não faz nada se for a mesma turma
    }
    
    // Indica que estamos carregando a nova turma
    setIsLoading(true);
    
    // Reset da flag para permitir nova requisição
    setDataLoadedOnce(false);
    
    console.log("DEBUG - handleClassChange - classItem:", classItem);
    console.log("DEBUG - handleClassChange - average_grade (original):", classItem.average_grade, "tipo:", typeof classItem.average_grade);
    
    const parsedAverage = parseInt(String(classItem.average_grade)) || 0;
    console.log("DEBUG - handleClassChange - parsedAverage:", parsedAverage, "tipo:", typeof parsedAverage);
    
    // Cria um objeto inicial para a nova turma selecionada
    const initialClass: ClassData = {
      id: classItem.id,
      name: classItem.name,
      average_grade: parsedAverage,
      students: [],
      competencies: []
    };
    
    console.log("DEBUG - handleClassChange - initialClass criado:", initialClass);
    
    // Atualiza o estado
    setSelectedClass(initialClass);
    
    // Define o ID para acionar a busca de dados no ProfessorDataFetcher
    setSelectedClassId(classItem.id);
    console.log("Nova turma selecionada:", classItem.name, "ID:", classItem.id, classItem.average_grade, "Nota media");
  };

  // Enquanto os dados iniciais não forem carregados, exibe uma tela de loading
  if (initialLoading) {
    return (
      <Layout role="professor" background="#fff">
        {/* Componente que busca os dados e chama handleClassesLoaded quando concluir */}
        <ProfessorDataFetcher 
          onClassesLoaded={handleClassesLoaded}
          onClassDataLoaded={handleClassDataLoaded} 
          classId={selectedClassId || undefined}
        />
        <div className={styles.loadingContainer}>
          <div className={styles.loadingContent}>
            <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} />
          </div>
        </div>
      </Layout>
    )
  }

  // Define quais alunos serão exibidos: todos ou apenas os 4 primeiros
  const studentsToShow = showAllStudents
    ? selectedClass?.students || []
    : selectedClass?.students?.slice(0, 4) || []
    
  // CSS para o indicador de carregamento
  const loadingStyles = `
  .${styles.loadingContainer} {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    width: 100%;
    background-color: #ffffff;
  }
  
  .${styles.loadingContent} {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    color: black;
  }
  
  .${styles.loadingLogo} {
    width: 100px;
    height: 50px;
    animation: pulse 1.5s infinite ease-in-out;
  }
  
  .${styles.loadingText} {
    margin-top: 20px;
    font-size: 16px;
    color: #333;
  }
  
  @keyframes pulse {
    0% { transform: scale(0.95) rotate(0deg); opacity: 0.7; }
    50% { transform: scale(1.05) rotate(180deg); opacity: 1; }
    100% { transform: scale(0.95) rotate(360deg); opacity: 0.7; }
  }
  
  .${styles.smallLoading} {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #3498db;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-left: 10px;
    vertical-align: middle;
  }
  
  .${styles.gradeInfo} {
    font-size: 0.8rem;
    color: #666;
    margin-top: 5px;
    display: flex;
    justify-content: space-between;
  }
  
  .${styles.gradeTurma} {
    font-weight: bold;
  }
  
  .${styles.gradeId} {
    color: #999;
    font-size: 0.7rem;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

  return (
    <>
      <style>{loadingStyles}</style>
      <RouteGuard 
        requiredRole="professor"
        fallback={
          <div className="flex h-screen w-full items-center justify-center bg-gray-100">
            <div className="text-center">
              <div className="mb-4">Verificando permissões...</div>
              <div>Se você não for redirecionado, <button 
                onClick={() => window.location.href="/dashboard"} 
                className="text-blue-500 underline">clique aqui</button>
              </div>
            </div>
          </div>
        }
      >
        <Layout role="professor" background="#f5f5f5">
          {/* Componente invisível que lida com as requisições de dados */}
          <ProfessorDataFetcher 
            onClassesLoaded={handleClassesLoaded}
            onClassDataLoaded={handleClassDataLoaded}
            classId={selectedClassId || undefined}
            disabled={dataLoadedOnce && !isLoading} // Desabilita requisições desnecessárias
          />
          
          {isLoading ? (
            // Mostrar loading enquanto troca de turma
            <div className={styles.loadingContainer}>
              <div className={styles.loadingContent}>
                <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} />
              </div>
            </div>
          ) : (
            <div className={styles.container}>
              {/* Middle Section */}
              <div className={styles.middleSection}>
                {/* Class Selector */}
                <div className={styles.selectorCard}>
                  <h2 className={styles.sectionTitle}>Selecione uma Turma:</h2>
                  <div className={styles.dropdown}>
                    <button className={styles.dropdownButton} onClick={() => setIsDropdownOpen(!isDropdownOpen)}>
                      <ChevronDown className={styles.dropdownIcon} />
                      <span>{selectedClass?.name}</span>
                    </button>
                    {isDropdownOpen && (
                      <div className={styles.dropdownMenu}>
                        {apiClasses.map((classItem) => (
                          <div
                            key={classItem.id}
                            className={styles.dropdownItem}
                            onClick={() => handleClassChange(classItem)}
                          >
                            {classItem.name}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Botão para criar novo tema */}
                <button
                  className={styles.createThemeButton}
                  onClick={() => setIsThemeModalOpen(true)}
                >
                  <PenLine size={20} />
                  <span>Criar Novo Tema</span>
                </button>

                {/* Average Grade Card */}
                <div className={styles.gradeCard}>
                  <h2 className={styles.sectionTitle}>
                    Nota Média:
                  </h2>
                  <div className={styles.gradeValue}>
                    {formatAverage(selectedClass?.average_grade)}
                    <span className={styles.gradeMax}>/1000</span>
                  </div>
                  <div className={styles.gradeInfo}>
                    <span>Turma: {selectedClass?.name}</span>
                  </div>
                </div>

                {/* Students List */}
                <div className={styles.studentsCard}>
                  <h2 className={styles.sectionTitle}>
                    Alunos:
                  </h2>
                  <div className={styles.studentsHeader}>
                    <div className={styles.studentNameHeader}>• Nome do Aluno</div>
                    <div className={styles.studentGradeHeader}>• Nota Média</div>
                    <div className={styles.studentReportHeader}>• Relatório</div>
                  </div>
                  <div className={styles.studentsList}>
                    {studentsToShow.map((student, index) => (
                      <div key={`${student.id || student.student_user_id || index}-${index}`} className={styles.studentItem}>
                        <div className={styles.studentNumber}>{String(index + 1).padStart(2, "0")}</div>
                        <div className={styles.studentName}>{student.name}</div>
                        <div 
                          className={styles.studentGrade} 
                          style={{ 
                            color: getGradeColor(student.grade || student.average_grade || 0) 
                          }}
                        >
                          {student.grade || student.average_grade || 0}
                        </div>
                        <button 
                          className={styles.reportButton}
                          onClick={(e) => {
                            e.preventDefault();
                            handleReportClick(student);
                          }}
                        >
                          <FileText size={18} />
                        </button>
                      </div>
                    ))}
                  </div>
                  {selectedClass && selectedClass.students && selectedClass.students.length > 4 && (
                    <div className={styles.showMoreContainer}>
                      <button className={styles.showMoreButton} onClick={() => setShowAllStudents(!showAllStudents)}>
                        {showAllStudents ? "Ver menos" : "Ver mais"}
                      </button>
                    </div>
                  )}
                  <div className={styles.gradeInfo}>
                    <span>Turma: {selectedClass?.name}</span>
                  </div>
                </div>
              </div>

              {/* Right Section */}
              <div className={styles.rightSection}>
                {/* Competency Performance */}
                <div className={styles.competencyCard}>
                  <div className={styles.competencyChart}>
                    <h2 className={styles.sectionTitle}>
                      Desempenho de Competências:
                    </h2>
                    <div className={styles.competencyChartContent}>
                      <div className={styles.competencyGridLines}>
                        <div className={styles.verticalLine} style={{ left: "0%" }}></div>
                        <div className={styles.verticalLine} style={{ left: "25%" }}></div>
                        <div className={styles.verticalLine} style={{ left: "50%" }}></div>
                        <div className={styles.verticalLine} style={{ left: "75%" }}></div>
                        <div className={styles.verticalLine} style={{ left: "100%" }}></div>
                      </div>
                      {selectedClass?.competencies && selectedClass.competencies.map((competency) => (
                        <div key={competency.id} className={styles.competencyItem}>
                          <div className={styles.competencyNumber}>{competency.id}</div>
                          <div className={styles.competencyBarContainer}>
                            <div
                              className={styles.competencyBar}
                              style={{
                                width: `${(competency.value / 200) * 100}%`,
                                backgroundColor: competency.color,
                              }}
                            >
                              <span className={styles.competencyValue}>{competency.value}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className={styles.competencyScale}>
                      <span>0</span>
                      <span>50</span>
                      <span>100</span>
                      <span>150</span>
                      <span>200</span>
                    </div>
                  </div>
                  <div className={styles.competencyLegend}>
                    {selectedClass?.competencies && selectedClass.competencies.map((competency) => (
                      <div key={competency.id} className={styles.legendItem}>
                        <div className={styles.legendColor} style={{ backgroundColor: competency.color }}></div>
                        <div className={styles.legendText}>
                          {competency.id}: {competency.name}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className={styles.gradeInfo}>
                    <span>Turma: {selectedClass?.name}</span>
                  </div>
                </div>

                {/* General Performance - Gráfico de turmas */}
                <div className={styles.performanceCard}>
                  <h2 className={styles.sectionTitle}>
                    Desempenho Geral das Turmas:
                  </h2>
                  <div className={styles.performanceContent}>
                    <div className={styles.performanceHeader}>
                      <div>Nota Média</div>
                    </div>
                    <div className={styles.performanceChartWrapper}>
                      <div className={styles.performanceGridLines}>
                        <div className={styles.gridLine}>1000</div>
                        <div className={styles.gridLine}>800</div>
                        <div className={styles.gridLine}>600</div>
                        <div className={styles.gridLine}>400</div>
                        <div className={styles.gridLine}>200</div>
                        <div className={styles.gridLine}>0</div>
                      </div>
                      <div className={styles.performanceChartContainer}>
                      {apiClasses.map((classItem, index) => {
                        const avgGrade = parseInt(String(classItem.average_grade || 0));
                        
                        // Quebra o nome da turma em palavras para exibir uma por linha
                        const words = classItem.name.split(' ');
                        
                        return (
                          <div key={classItem.id} className={styles.studentBarColumn}>
                            <div className={styles.studentBarBackground}></div>
                            <div
                              className={styles.studentBar}
                              style={{
                                height: `${Math.max(5, (avgGrade / 1000) * 100)}%`,
                                backgroundColor: getGradeColor(avgGrade),
                              }}
                            >
                              <span className={styles.studentBarValue}>{avgGrade}</span>
                            </div>
                            <div 
                              className={styles.studentBarLabel} 
                              title={classItem.name}
                            >
                              {/* Renderiza cada palavra em uma nova linha */}
                              {words.map((word, wordIndex) => (
                                <div key={wordIndex} className={styles.wordBreak}>
                                  {word}
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                      </div>
                    </div>
                    <div className={styles.performanceFooter}>
                      <div>Turmas</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Modal de seleção de redações do aluno */}
          {isEssayModalOpen && (
            <div className={styles.modalOverlay}>
              <div className={styles.modalContent}>
                <div className={styles.modalHeader}>
                  <h2>Redações de {selectedStudent?.name}</h2>
                  <button className={styles.closeButton} onClick={() => setIsEssayModalOpen(false)}>
                    <X size={20} />
                  </button>
                </div>

                <div className={styles.modalBody}>
                  {essaysLoading ? (
                    <div className={styles.loadingContent} style={{ padding: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                      <div style={{ width: '60px', height: '60px', margin: '0 auto 16px' }}>
                        <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} style={{ width: '100%', height: '100%' }} />
                      </div>
                      <p>Carregando redações...</p>
                    </div>
                  ) : (
                    <>
                      {studentEssays && studentEssays.essays && Object.keys(studentEssays.essays).length > 0 ? (
                        <div className={styles.essayGrid}>
                          {Object.entries(studentEssays.essays).map(([id, essay], index) => (
                            <button
                              key={id}
                              className={styles.essayButton}
                              onClick={() => handleEssaySelect(id)}
                            >
                              <div className={styles.essayButtonContent}>
                                <span
                                  className={styles.essayButtonIcon}
                                  style={{ 
                                    backgroundColor: 
                                      essay.overall_grade >= 800 ? "#3ADAA8" : 
                                      essay.overall_grade >= 600 ? "#F59E0B" : "#EF4444" 
                                  }}
                                >
                                  {String(index + 1).padStart(2, "0")}
                                </span>
                                <div className={styles.essayButtonInfo}>
                                  <span className={styles.essayButtonTitle}>
                                    {essay.theme
                                      ? essay.theme.length > 30
                                        ? `${essay.theme.slice(0, 30)}...`
                                        : essay.theme
                                      : "Sem tema"}
                                  </span>
                                  <span className={styles.essayButtonGrade}>
                                    Nota: {essay.overall_grade}/1000
                                  </span>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className={styles.noEssaysMessage}>
                          Este aluno ainda não tem redações enviadas
                        </p>
                      )}
                    </>
                  )}
                </div>

                <div className={styles.modalFooter}>
                  <button className={styles.modalCancelButton} onClick={() => setIsEssayModalOpen(false)}>
                    Fechar
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Modal de correção de redação */}
          {selectedStudent && (
            <CorrecaoProfessorModal
              isOpen={isCorrectionModalOpen}
              onClose={() => setIsCorrectionModalOpen(false)}
              studentId={selectedStudent.id || selectedStudent.student_user_id || ""}
              essayId={selectedEssayId}
            />
          )}

          {/* Modal para criar novo tema */}
          {isThemeModalOpen && (
            <div className={styles.modalOverlay}>
              <div className={styles.modalContent} style={{ maxWidth: '500px' }}>
                <div className={styles.modalHeader}>
                  <h2>Criar Novo Tema de Redação</h2>
                  <button className={styles.closeButton} onClick={() => setIsThemeModalOpen(false)}>
                    <X size={20} />
                  </button>
                </div>

                <div className={styles.modalBody}>
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: 'black' }}>
                      Título do Tema:
                    </label>
                    <input
                      type="text"
                      value={themeTitle}
                      onChange={(e) => setThemeTitle(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '10px',
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px',
                        fontSize: '14px',
                        color: 'black'
                      }}
                      placeholder="Digite o título do tema"
                    />
                  </div>

                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: 'black' }}>
                      Descrição (opcional):
                    </label>
                    <textarea
                      value={themeDescription}
                      onChange={(e) => setThemeDescription(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '10px',
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px',
                        fontSize: '14px',
                        minHeight: '100px',
                        resize: 'vertical',
                        color: 'black'
                      }}
                      placeholder="Digite a descrição ou detalhes adicionais do tema"
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: 'black' }}>
                      Aplicar nas turmas:
                    </label>
                    <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '8px' }}>
                      {apiClasses.map((classItem) => (
                        <label key={classItem.id} className={styles.checkboxContainer}>
                          <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={!!selectedClasses[classItem.id]}
                            onChange={() => handleClassSelection(classItem.id)}
                          />
                          <span className={styles.checkboxLabel}>{classItem.name}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  {themeResult && (
                    <div className={themeResult.success ? styles.successMessage : styles.errorMessage}>
                      {themeResult.message}
                    </div>
                  )}
                </div>

                <div className={styles.modalFooter}>
                  <button
                    className={styles.modalCancelButton}
                    onClick={() => setIsThemeModalOpen(false)}
                    disabled={isSubmittingTheme}
                  >
                    Cancelar
                  </button>
                  <button
                    style={{
                      backgroundColor: '#4361EE',
                      color: 'white',
                      fontWeight: '600',
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: 'none',
                      cursor: 'pointer',
                      marginLeft: '10px'
                    }}
                    onClick={handleSubmitTheme}
                    disabled={isSubmittingTheme}
                  >
                    {isSubmittingTheme ? 'Enviando...' : 'Criar Tema'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </Layout>
      </RouteGuard>
    </>
  )
}