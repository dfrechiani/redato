"use client";

import { useEffect, useState } from "react";
import { MessageCircle, X } from "lucide-react";
import Layout from "../dashboard/components/Layout";
import styles from "./study-plan.module.css";
import ChatWidget from "./chat-widget";
import { useRouter } from "next/navigation";

// 1) Interfaces
interface CorrectionData {
  overall_grade: number | string;
  detailed_analysis?: string;
  competencies?: {
    competency: string;
    grade: number;
    errors?: {
      error_type: string;
      suggestion: string;
      snippet: string;
      explanation?: string;
      justification?: string;
    }[];
  }[];
  full_essay?: string;
  essay_id?: string;
}

// Interface para os dados de cada redação
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

// Interface para os dados do dashboard
interface DashboardData {
  total_essays: number;
  average_grade: number;
  competency_averages: {
    [competencyName: string]: number;
  };
  essays?: {
    [essayId: string]: EssayData;
  };
}

// Modal de seleção de redações
const EssaySelectionModal = ({
  isOpen,
  onClose,
  essays,
  onSelect,
}: {
  isOpen: boolean;
  onClose: () => void;
  essays: { [id: string]: EssayData } | undefined;
  onSelect: (id: string) => void;
}) => {
  const colors = [
    "#2E7BF3", // Azul
    "#9FE870", // Verde
    "#9333EA", // Roxo
    "#84CC16", // Lima
    "#E5E7EB", // Cinza
  ];

  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <h2>Selecione uma redação para analisar</h2>
          <button className={styles.closeButton} onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className={styles.modalBody}>
          {essays && Object.keys(essays).length > 0 ? (
            <div className={styles.essayGrid}>
              {Object.entries(essays).map(([id, essay], index) => (
                <button
                  key={id}
                  className={styles.essayButton}
                  onClick={() => onSelect(id)}
                >
                  <div className={styles.essayButtonContent}>
                    <span
                      className={styles.essayButtonIcon}
                      style={{ backgroundColor: colors[index % colors.length] }}
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
              Você ainda não tem redações enviadas
            </p>
          )}
        </div>

        <div className={styles.modalFooter}>
          <button className={styles.modalCancelButton} onClick={onClose}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
};

interface ProfessorFeedback {
  feedback_text: string;
  updated_at: string | null;
}

export default function StudyPlanPage() {
  // 2) Estados locais
  const [correctionData, setCorrectionData] = useState<CorrectionData | null>(null);
  const [selectedCompetency, setSelectedCompetency] = useState<string | null>(null);
  const [selectedError, setSelectedError] = useState<number | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [professorFeedback, setProfessorFeedback] =
    useState<ProfessorFeedback | null>(null);

  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  const router = useRouter();

  useEffect(() => {
    const essayId = correctionData?.essay_id;
    if (!essayId) {
      setProfessorFeedback(null);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/${essayId}/professor-feedback`
        );
        if (!response.ok) return;
        const payload = await response.json();
        if (cancelled) return;
        if (payload?.data?.feedback_text) {
          setProfessorFeedback({
            feedback_text: payload.data.feedback_text,
            updated_at: payload.data.updated_at || null,
          });
        } else {
          setProfessorFeedback(null);
        }
      } catch (err) {
        console.error("Erro ao carregar feedback do professor:", err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [correctionData?.essay_id]);

  // 3) Carrega os dados da correção do localStorage
  useEffect(() => {
    const storedData = localStorage.getItem("correctionData");
    if (storedData) {
      try {
        const parsedData: CorrectionData = JSON.parse(storedData);
        console.log("📚 Dados carregados no Plano de Estudos:", parsedData);
        setCorrectionData(parsedData);
        if (parsedData.competencies && parsedData.competencies.length > 0) {
          setSelectedCompetency(parsedData.competencies[0].competency);
        }
        setIsLoading(false);
      } catch (error) {
        console.error("Erro ao parsear correctionData:", error);
        setIsLoading(false);
      }
    } else {
      console.warn("correctionData não encontrado no localStorage");
      // Se não houver dados no localStorage, busca os dados do dashboard
      fetchDashboardData();
    }
  }, []);

  // Função para buscar dados do dashboard
  const fetchDashboardData = async () => {
    try {
      setIsLoading(true);
      
      if (!userId) {
        console.error("Usuário não autenticado!");
        setIsLoading(false);
        return Promise.reject("Usuário não autenticado");
      }

      console.log("📡 Fazendo requisição para:", `${process.env.NEXT_PUBLIC_API_BASE_URL}/dashboard/user?user_id=${userId}`);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/dashboard/user?user_id=${userId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });
      
      if (!response.ok) {
        throw new Error("Erro ao buscar dados do dashboard");
      }
      
      const data: DashboardData = await response.json();
      setDashboardData(data);
      
      // Se a função for chamada diretamente ao carregar a página e não houver dados
      // de correção, abre a modal
      if (!correctionData && data.essays && Object.keys(data.essays).length > 0) {
        setIsModalOpen(true);
      }
      
      setIsLoading(false);
      return Promise.resolve(data);
    } catch (error) {
      console.error("Erro ao buscar dados do dashboard:", error);
      setIsLoading(false);
      return Promise.reject(error);
    }
  };

  // Função para selecionar redação do dashboard e buscar correção completa
  const handleEssaySelection = async (essayId: string) => {
    setIsLoading(true);
    
    try {
      // Usa o mesmo endpoint que é usado após submeter uma redação
      const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/result/essay/${essayId}`;
      console.log("📡 Buscando dados completos da correção:", url);
      
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Erro ao buscar correção: ${response.status}`);
      }
      
      const result = await response.json();
      
      // Verifica se temos dados válidos
      if (!result.data && !result.overall_grade) {
        throw new Error("Dados de correção não encontrados");
      }
      
      const correctionData = result.data || result;
      
      // Adiciona essay_id se não existir
      if (!correctionData.essay_id) {
        correctionData.essay_id = essayId;
      }
      
      // Busca o conteúdo completo da redação
      if (correctionData.essay_id && !correctionData.full_essay) {
        try {
          const contentResponse = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/content/${correctionData.essay_id}`);
          if (contentResponse.ok) {
            const contentData = await contentResponse.json();
            correctionData.full_essay = contentData.content || contentData.text || contentData.essay || "";
          }
        } catch (err) {
          console.error("Erro ao buscar conteúdo da redação:", err);
        }
      }
      
      // Salva no localStorage
      localStorage.setItem("correctionData", JSON.stringify(correctionData));
      
      // Atualiza o estado
      setCorrectionData(correctionData);
      
      // Seleciona a primeira competência
      if (correctionData.competencies && correctionData.competencies.length > 0) {
        setSelectedCompetency(correctionData.competencies[0].competency);
      }
      
      setIsModalOpen(false);
    } catch (error) {
      console.error("Erro ao buscar correção completa:", error);
      
      // Fallback: usa os dados do dashboard se a API falhar
      if (dashboardData?.essays && dashboardData.essays[essayId]) {
        console.log("Usando dados do dashboard como fallback");
        
        const essayData = dashboardData.essays[essayId];
        
        // Converte para o formato de correção
        const fallbackCorrection: CorrectionData = {
          overall_grade: essayData.overall_grade,
          detailed_analysis: essayData.theme || "Análise detalhada não disponível",
          competencies: Object.entries(essayData.competencies).map(([name, data]) => ({
            competency: name,
            grade: data.grade,
            justification: data.detailed_analysis || data.justification || "Justificativa não disponível",
            errors: []
          })),
          essay_id: essayId
        };
        
        // Tenta buscar o conteúdo da redação
        try {
          const contentResponse = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/content/${essayId}`);
          if (contentResponse.ok) {
            const contentData = await contentResponse.json();
            fallbackCorrection.full_essay = contentData.content || contentData.text || contentData.essay || "";
          }
        } catch (err) {
          console.error("Erro ao buscar conteúdo da redação:", err);
        }
        
        localStorage.setItem("correctionData", JSON.stringify(fallbackCorrection));
        setCorrectionData(fallbackCorrection);
        
        if (fallbackCorrection.competencies && fallbackCorrection.competencies.length > 0) {
          setSelectedCompetency(fallbackCorrection.competencies[0].competency);
        }
      } else {
        alert("Não foi possível carregar os dados desta redação");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // 4) Se houver essay_id e a redação ainda não foi carregada, busca o conteúdo da redação
  useEffect(() => {
    if (correctionData?.essay_id && !correctionData.full_essay) {
      const fetchEssayContent = async () => {
        try {
          const response = await fetch(
            `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/content/${correctionData.essay_id}`
          );
          if (!response.ok) {
            throw new Error("Erro ao buscar conteúdo da redação");
          }
          const data = await response.json();
          console.log("Conteúdo da redação:", data);
          // Supondo que o endpoint retorne o conteúdo em data.content
          setCorrectionData((prev) =>
            prev ? { ...prev, full_essay: data.content } : prev
          );
        } catch (error) {
          console.error("Erro ao buscar conteúdo da redação:", error);
        }
      };
      fetchEssayContent();
    }
  }, [correctionData?.essay_id]);

  // 5) Função que retorna o trecho do erro selecionado
  function getSelectedErrorSnippet(): string {
    if (!selectedCompetency || selectedError == null) return "";
    const comp = correctionData?.competencies?.find(
      (c) => c.competency === selectedCompetency
    );
    if (!comp || !comp.errors) return "";
    const err = comp.errors[selectedError];
    return err ? err.snippet : "";
  }
  const selectedErrorSnippet = getSelectedErrorSnippet();

  // 6) Função que retorna a redação com destaque (marca com <mark> o trecho selecionado)
  function getHighlightedEssay(): string {
    const originalText = correctionData?.full_essay || "";
    if (!selectedErrorSnippet) {
      return originalText;
    }
    // Escapa os caracteres especiais para uso na expressão regular
    const safeSnippet = selectedErrorSnippet.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Procura a primeira ocorrência (case-insensitive)
    const regex = new RegExp(safeSnippet, "i");
    return originalText.replace(
      regex,
      `<mark id="highlighted-snippet" class="${styles.highlight}">$&</mark>`
    );
  }
  const highlightedEssayHTML = getHighlightedEssay();

  // Nova função para formatar o texto com parágrafos
  function formatEssayWithParagraphs(html: string): string {
    // Normaliza as quebras de linha
    const normalized = html.replace(/\r\n/g, "\n");
    // Divide o texto em parágrafos onde houver quebras de linha duplas ou mais
    const paragraphs = normalized.split(/\n\s*\n/);
    // Envolve cada parágrafo com <p> e junta novamente
    return paragraphs.map((para) => `<br /><p>${para.trim()}</p>`).join("");
  }

  // 7) Após renderizar o texto destacado, rolar até o trecho marcado
  useEffect(() => {
    if (!selectedErrorSnippet) return;
    const timer = setTimeout(() => {
      const snippetEl = document.getElementById("highlighted-snippet");
      if (snippetEl) {
        snippetEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedErrorSnippet, highlightedEssayHTML]);

  // 8) Helpers para a interface
  function handleCompetencyClick(competency: string) {
    setSelectedCompetency(competency);
    setSelectedError(null);
  }

  function handleErrorClick(index: number) {
    setSelectedError(index);
  }

  function getErrorClass(errorCount: number) {
    if (errorCount >= 5 || errorCount === 4) return styles.red;
    if (errorCount === 1 || errorCount === 2 || errorCount === 3) return styles.yellow;
    if (errorCount === 0) return styles.green;
    return "";
  }

  function truncate(text: string, maxLength: number) {
    return text.length > maxLength ? text.substring(0, maxLength) + "..." : text;
  }

  // 9) Enquanto os dados ou a redação não estiverem prontos, exibe um loading de página inteira
  if (isLoading) {
    return (
      <Layout background="#fff">
        <div className={styles.loadingContainer}>
          <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} />
        </div>
      </Layout>
    );
  }

  // Se não há correção selecionada e não tem modal aberta
  if (!correctionData && !isModalOpen) {
    return (
      <Layout background="#fff">
        <div className={styles.noDataContainer}>
          <h2>Nenhuma redação selecionada</h2>
          <button 
            className={styles.selectEssayButton}
            onClick={() => {
              if (dashboardData?.essays && Object.keys(dashboardData.essays).length > 0) {
                setIsModalOpen(true);
              } else {
                router.push('/dashboard');
              }
            }}
          >
            {dashboardData?.essays && Object.keys(dashboardData.essays).length > 0 
              ? "Selecionar redação" 
              : "Voltar ao dashboard"}
          </button>
        </div>
      </Layout>
    );
  }

  // Renderiza a modal caso esteja aberta mas sem dados de correção
  if (!correctionData && isModalOpen) {
    return (
      <Layout background="#fff">
        <EssaySelectionModal 
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            router.push('/dashboard');
          }}
          essays={dashboardData?.essays}
          onSelect={handleEssaySelection}
        />
        
        <div className={styles.noDataContainer}>
          <h2>Selecione uma redação para analisar</h2>
        </div>
      </Layout>
    );
  }

  // Se não tem o conteúdo completo da redação, continua mostrando loading
  if (!correctionData?.full_essay) {
    return (
      <Layout background="#fff">
        <div className={styles.loadingContainer}>
          <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} />
        </div>
      </Layout>
    );
  }

  // 10) Renderização da página de Plano de Estudo
  return (
    <Layout background="url('/bg-redato.png') no-repeat center center fixed">
      <EssaySelectionModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        essays={dashboardData?.essays}
        onSelect={handleEssaySelection}
      />

      <div className={styles.studyPlanContainer}>
        <div className={styles.studyHeader}>
          <h2>Jornada de Aprendizado</h2>
          <button
            className={styles.selectAnotherButton}
            onClick={() => {
              fetchDashboardData().then(() => {
                setIsModalOpen(true);
              });
            }}
          >
            SELECIONAR OUTRA REDAÇÃO
          </button>
        </div>

        {professorFeedback && (
          <div
            style={{
              margin: "0 0 16px 0",
              padding: "16px 20px",
              background: "#F0F9FF",
              border: "1px solid #BAE6FD",
              borderRadius: "8px",
            }}
          >
            <h3
              style={{
                margin: "0 0 8px 0",
                fontSize: "15px",
                fontWeight: 600,
                color: "#0369A1",
              }}
            >
              Feedback do Professor
            </h3>
            <p
              style={{
                margin: 0,
                whiteSpace: "pre-wrap",
                color: "#0C4A6E",
                fontSize: "14px",
                lineHeight: 1.5,
              }}
            >
              {professorFeedback.feedback_text}
            </p>
            {professorFeedback.updated_at && (
              <p
                style={{
                  margin: "8px 0 0 0",
                  fontSize: "12px",
                  color: "#64748B",
                }}
              >
                Atualizado em{" "}
                {new Date(professorFeedback.updated_at).toLocaleString("pt-BR")}
              </p>
            )}
          </div>
        )}

        {/* Lista de Competências */}
        <div className={styles.competencyList}>
          {correctionData?.competencies?.map((comp, index) => {
            const errorCount = comp.errors?.length || 0;
            return (
              <button
                key={index}
                className={`${styles.competencyButton} ${getErrorClass(errorCount)} ${
                  selectedCompetency === comp.competency ? styles.active : ""
                }`}
                onClick={() => handleCompetencyClick(comp.competency)}
              >
                {comp.competency} <span>({errorCount})</span>
              </button>
            );
          })}
        </div>

        <div className={styles.mainContent}>
          {/* Seção de Erros */}
          {selectedCompetency && (
            <div className={styles.errorSection}>
              <div className={styles.sectionHeader}>
                <h3>Trecho em Foco</h3>
                {/* O botão de interação só aparece se um erro estiver selecionado */}
                {selectedError !== null && (
                  <button
                    className={styles.interactButton}
                    onClick={() => setShowChat(true)}
                  >
                  </button>
                )}
              </div>

              <div className={styles.errorCont}>
                {/* Lista de erros para a competência selecionada */}
                <div className={styles.errorList}>
                  {correctionData?.competencies
                    ?.find((c) => c.competency === selectedCompetency)
                    ?.errors?.map((err, idx) => (
                      <div
                        key={idx}
                        className={`${styles.errorItem} ${
                          selectedError === idx ? styles.selectedError : ""
                        }`}
                        onClick={() => handleErrorClick(idx)}
                      >
                        <strong>ERRO {idx + 1}:</strong> "
                        {truncate(err.snippet, 30)}"
                      </div>
                    ))}
                </div>

                {/* Detalhes do erro selecionado */}
                {selectedError !== null && (
                  <div className={styles.errorDetails}>
                    <p>
                      <strong className={styles.titleDetails}>Trecho em foco: </strong>
                      "
                      {
                        correctionData?.competencies
                          ?.find((c) => c.competency === selectedCompetency)
                          ?.errors[selectedError].snippet
                      }
                      "
                    </p>
                    <hr className={styles.line} />
                    <p>
                      <strong className={styles.titleDetails}>Tipo de erro:</strong>{" "}
                      {
                        correctionData?.competencies
                          ?.find((c) => c.competency === selectedCompetency)
                          ?.errors[selectedError].error_type
                      }
                    </p>
                    {correctionData?.competencies
                      ?.find((c) => c.competency === selectedCompetency)
                      ?.errors[selectedError].explanation && (
                      <p>
                        <strong className={styles.titleDetails}>Explicação:</strong>{" "}
                        {
                          correctionData?.competencies
                            ?.find((c) => c.competency === selectedCompetency)
                            ?.errors[selectedError].explanation
                        }
                      </p>
                    )}
                    <hr className={styles.line} />
                    <p>
                      <strong className={styles.titleDetails}>Correção:</strong>{" "}
                      {
                        correctionData?.competencies
                          ?.find((c) => c.competency === selectedCompetency)
                          ?.errors[selectedError].suggestion
                      }
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Seção da Redação */}
          <div className={styles.essaySection}>
            <h3>Sua Redação</h3>
            <div
              className={styles.essayContent}
              dangerouslySetInnerHTML={{
                __html: formatEssayWithParagraphs(highlightedEssayHTML)
              }}
            />
          </div>
        </div>
      </div>

      {/* Chat overlay */}
      {showChat &&
        correctionData &&
        selectedCompetency &&
        selectedErrorSnippet &&
        userId && (
          <div className={styles.chatOverlay}>
            <ChatWidget
              competency={selectedCompetency}
              errorSnippet={selectedErrorSnippet}
              errorType={
                correctionData?.competencies?.find((c) => c.competency === selectedCompetency)
                  ?.errors[selectedError!].error_type || ""
              }
              userId={userId}
              essay_id={correctionData.essay_id}
              onClose={() => setShowChat(false)}
            />
          </div>
        )}
    </Layout>
  );
}