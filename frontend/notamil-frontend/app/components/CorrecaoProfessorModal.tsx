"use client";

import React, { useEffect, useState, useRef } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import styles from "../correcao/correcao.module.css";
import studyPlanStyles from "../study-plan/study-plan.module.css";
import { auth } from "@/services/firebaseClient";

const MAX_FEEDBACK_LENGTH = 5000;

interface Competency {
  competency: string;
  grade: number;
  justification: string;
  errors: any[];
}

interface CorrectionData {
  overall_grade: number;
  detailed_analysis: string;
  competencies: Competency[];
  essay_id?: string;
  full_essay?: string;
}

interface CriteriaProps {
  title: string;
  score: number;
  total: number;
  color?: "blue" | "green" | "red";
  feedback?: string;
  progress?: string;
  isOpen: boolean;
  onToggle: () => void;
}

// Componente de Critérios para os acordeões de competências
const Criteria: React.FC<CriteriaProps> = ({
  title,
  score,
  total,
  color = "green",
  feedback,
  progress,
  isOpen,
  onToggle,
}) => {
  // Calcula a largura da barra de progresso em %
  const progressWidth = `${(score / total) * 100}%`;

  return (
    <div className={styles.criteria_item}>
      <button className={styles.criteria_header} onClick={onToggle}>
        <div className={styles.criteria_title_wrapper}>
          {feedback &&
            (isOpen ? (
              <ChevronUp className={styles.chevron} />
            ) : (
              <ChevronDown className={styles.chevron} />
            ))}
          <h3 className={styles.criteria_title}>{title}</h3>
        </div>
        <span className={styles.criteria_score}>
          {score}
          <span className={styles.criteria_total}>/{total}</span>
        </span>
      </button>

      <div className={styles.progress_bar}>
        <div
          className={`${styles.progress_bar_fill} ${styles[color]}`}
          style={{ width: progressWidth }}
        />
      </div>

      {feedback && (
        <div
          className={`${styles.collapsible_content} ${
            isOpen ? styles.open : ""
          }`}
        >
          <div className={styles.feedback_content}>
            <p className={styles.feedback_text}>{feedback}</p>
            {progress && <p className={styles.progress_text}>{progress}</p>}
          </div>
        </div>
      )}
    </div>
  );
};

// Modal para exibir a correção da redação do aluno
const CorrecaoProfessorModal = ({
  isOpen,
  onClose,
  studentId,
  essayId,
}: {
  isOpen: boolean;
  onClose: () => void;
  studentId: string;
  essayId: string;
}) => {
  const [correctionData, setCorrectionData] = useState<CorrectionData | null>(null);
  const [openCriteria, setOpenCriteria] = useState<boolean[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDetailedView, setIsDetailedView] = useState(false);
  const [selectedCompetency, setSelectedCompetency] = useState<string | null>(null);
  const [selectedError, setSelectedError] = useState<number | null>(null);
  const [essayContent, setEssayContent] = useState<string>("");
  const [highlightedEssayHTML, setHighlightedEssayHTML] = useState<string>("");
  const [professorFeedback, setProfessorFeedback] = useState<string>("");
  const [savedFeedback, setSavedFeedback] = useState<string>("");
  const [isSavingFeedback, setIsSavingFeedback] = useState<boolean>(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackSavedAt, setFeedbackSavedAt] = useState<string | null>(null);

  // Referência para o elemento de conteúdo da redação para fazer scroll
  const essayContentRef = useRef<HTMLDivElement>(null);

  // Resetar o estado quando o modal é fechado
  useEffect(() => {
    if (!isOpen) {
      setIsDetailedView(false);
      setSelectedCompetency(null);
      setSelectedError(null);
      setProfessorFeedback("");
      setSavedFeedback("");
      setFeedbackError(null);
      setFeedbackSavedAt(null);
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && essayId) {
      setIsDetailedView(false); // Garante que sempre comece na visualização compacta
      fetchCorrectionData(essayId);
      fetchProfessorFeedback(essayId);
    }
  }, [isOpen, essayId]);

  const fetchProfessorFeedback = async (id: string) => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/${id}/professor-feedback`
      );
      if (!response.ok) {
        console.warn("Não foi possível carregar o feedback do professor.");
        return;
      }
      const payload = await response.json();
      const text = payload?.data?.feedback_text || "";
      setProfessorFeedback(text);
      setSavedFeedback(text);
      setFeedbackSavedAt(payload?.data?.updated_at || null);
    } catch (err) {
      console.error("Erro ao carregar feedback do professor:", err);
    }
  };

  const handleSaveFeedback = async () => {
    const trimmed = professorFeedback.trim();
    if (!trimmed) {
      setFeedbackError("O feedback não pode estar vazio.");
      return;
    }
    if (trimmed.length > MAX_FEEDBACK_LENGTH) {
      setFeedbackError(`O feedback deve ter no máximo ${MAX_FEEDBACK_LENGTH} caracteres.`);
      return;
    }

    setIsSavingFeedback(true);
    setFeedbackError(null);

    try {
      const currentUser = auth?.currentUser;
      if (!currentUser) {
        throw new Error("Sessão expirada. Faça login novamente.");
      }
      const token = await currentUser.getIdToken();

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/${essayId}/professor-feedback`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ feedback_text: trimmed }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Não foi possível salvar o feedback.");
      }

      setSavedFeedback(trimmed);
      setFeedbackSavedAt(new Date().toISOString());
    } catch (err: any) {
      setFeedbackError(err.message || "Erro ao salvar o feedback.");
    } finally {
      setIsSavingFeedback(false);
    }
  };

  const feedbackDirty = professorFeedback.trim() !== savedFeedback.trim();

  // Efeito para processar a redação quando um erro é selecionado
  useEffect(() => {
    if (correctionData && selectedCompetency && selectedError !== null) {
      const html = getHighlightedEssay();
      setHighlightedEssayHTML(html);
    }
  }, [correctionData, selectedCompetency, selectedError]);

  // Função para buscar os dados da correção
  const fetchCorrectionData = async (essayId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Usa o endpoint completo para buscar os dados da correção
      const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/result/essay/${essayId}`;
      console.log("📡 Buscando dados da correção:", url);
      
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Erro ao buscar correção: ${response.status}`);
      }
      
      const result = await response.json();
      
      console.log("Dados da correção recebidos:", result);
      
      // Verificar a estrutura dos dados recebidos
      const correctionData = result.data || result;
      
      // Garantir que temos um array de competências
      if (!correctionData.competencies) {
        correctionData.competencies = [];
      } else if (!Array.isArray(correctionData.competencies)) {
        // Se competências não for um array, tentar converter
        try {
          if (typeof correctionData.competencies === 'object') {
            correctionData.competencies = Object.entries(correctionData.competencies).map(([name, data]: [string, any]) => ({
              competency: name,
              grade: data.grade || 0,
              justification: data.justification || data.detailed_analysis || "",
              errors: data.errors || []
            }));
          }
        } catch (conversionError) {
          console.error("Erro ao converter competências:", conversionError);
          correctionData.competencies = [];
        }
      }
      
      // Atualiza o estado com os dados da correção
      setCorrectionData(correctionData);
      
      // Inicializa o array de "aberto/fechado" para cada competência
      if (correctionData.competencies && Array.isArray(correctionData.competencies)) {
        setOpenCriteria(correctionData.competencies.map(() => false));
        
        // Define a primeira competência como selecionada por padrão
        if (correctionData.competencies.length > 0) {
          setSelectedCompetency(correctionData.competencies[0].competency);
        }
      } else {
        // Fallback para caso não haja competências
        setOpenCriteria([]);
      }

      // Tenta obter o conteúdo completo da redação
      if (correctionData.full_essay) {
        setEssayContent(correctionData.full_essay);
      } else {
        // Tenta buscar o conteúdo da redação se não estiver disponível
        fetchEssayContent(essayId);
      }
    } catch (error) {
      console.error("Erro ao buscar dados da correção:", error);
      setError("Não foi possível carregar os dados da correção. Tente novamente.");
    } finally {
      setIsLoading(false);
    }
  };

  // Função para buscar o conteúdo da redação
  const fetchEssayContent = async (essayId: string) => {
    try {
      const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/content/${essayId}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        console.error("Não foi possível buscar o conteúdo da redação");
        return;
      }
      
      const data = await response.json();
      if (data.content) {
        setEssayContent(data.content);
      }
    } catch (error) {
      console.error("Erro ao buscar conteúdo da redação:", error);
    }
  };

  // Função para abrir/fechar os acordeões de competências
  const toggleCriteria = (index: number) => {
    setOpenCriteria((prev) => {
      const newState = [...prev];
      newState[index] = !newState[index];
      return newState;
    });
  };

  // Função para lidar com clique em uma competência
  const handleCompetencyClick = (competency: string) => {
    setSelectedCompetency(competency);
    setSelectedError(null);
  };

  // Função para lidar com clique em um erro
  const handleErrorClick = (index: number) => {
    setSelectedError(index === selectedError ? null : index);
    
    // Pequeno atraso para garantir que o HTML foi atualizado antes de tentar rolar
    setTimeout(() => {
      if (essayContentRef.current) {
        const highlightedElement = essayContentRef.current.querySelector(`.${studyPlanStyles.highlight}`);
        if (highlightedElement) {
          highlightedElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center'
          });
        }
      }
    }, 100);
  };

  // Função para obter o snippet do erro selecionado
  const getSelectedErrorSnippet = (): string => {
    if (!selectedCompetency || selectedError === null || !correctionData?.competencies) {
      return "";
    }
    const comp = correctionData.competencies.find((c) => c.competency === selectedCompetency);
    if (!comp || !comp.errors || !comp.errors[selectedError]) {
      return "";
    }
    return comp.errors[selectedError].snippet;
  };

  // Função para destacar os erros na redação
  const getHighlightedEssay = (): string => {
    if (!essayContent || !selectedCompetency || selectedError === null) {
      return essayContent;
    }

    let html = essayContent;
    const snippet = getSelectedErrorSnippet();
    
    if (snippet && html.includes(snippet)) {
      html = html.replace(
        snippet,
        `<span class="${studyPlanStyles.highlight}">${snippet}</span>`
      );
    }
    
    return html;
  };

  // Função para formatar a redação com parágrafos
  const formatEssayWithParagraphs = (html: string): string => {
    // Divide o conteúdo em parágrafos e os envolve em <p>
    return html
      .split("\n")
      .map((paragraph) => (paragraph.trim() ? `<p>${paragraph}</p>` : ""))
      .join("");
  };

  // Função para determinar a classe do erro com base na quantidade
  const getErrorClass = (errorCount: number) => {
    if (errorCount >= 4) return studyPlanStyles.red;
    if (errorCount >= 1 && errorCount <= 3) return studyPlanStyles.yellow;
    return studyPlanStyles.green;
  };

  // Função para truncar texto
  const truncate = (text: string, maxLength: number) => {
    return text.length > maxLength ? text.substring(0, maxLength) + "..." : text;
  };

  // Se a modal não estiver aberta, não renderiza nada
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay}>
      <div 
        className={styles.modalContent} 
        style={{ 
          maxWidth: isDetailedView ? '90%' : '800px', 
          maxHeight: '90vh', 
          overflowY: 'auto',
          width: isDetailedView ? '90%' : 'auto',
          height: isDetailedView ? '90vh' : 'auto'
        }}
      >
        <div className={styles.modalHeader}>
          <h2>{isDetailedView ? 'Feedback Detalhado da Redação' : 'Correção da Redação'}</h2>
          <button className={styles.closeButton} onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className={styles.modalBody} style={{ padding: '0' }}>
          {isLoading ? (
            <div style={{ padding: '40px', textAlign: 'center' }}>
              <div className={styles.smallLoading} style={{ width: '32px', height: '32px', margin: '0 auto 20px' }}></div>
              <p>Carregando dados da correção...</p>
            </div>
          ) : error ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#EF4444' }}>
              <p>{error}</p>
              <button 
                onClick={() => fetchCorrectionData(essayId)}
                style={{ 
                  marginTop: '20px',
                  padding: '8px 16px',
                  background: '#E5E7EB',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer'
                }}
              >
                Tentar novamente
              </button>
            </div>
          ) : correctionData ? (
            <>
              {!isDetailedView ? (
                // Visualização compacta (original)
                <div 
                  className={styles.feedback_container} 
                  style={{ 
                    margin: '0', 
                    boxShadow: 'none', 
                    borderRadius: '0',
                    padding: isDetailedView ? '40px' : '20px'
                  }}
                >
                  <div className={styles.score_section}>
                    <div className={styles.flex}>
                      <h2 className={styles.score_label}>NOTA</h2>
                      <div className={styles.gradeCard}>
                        <div className={styles.gradeValue}>
                          {Math.round(correctionData.overall_grade as number || 0)}
                          <span className={styles.gradeMax}>/1000</span>
                        </div>
                      </div>
                    </div>
                    <p className={styles.score_subtitle}>
                      {correctionData.detailed_analysis}
                    </p>
                  </div>

                  {/* Feedback editável do professor */}
                  <div style={{ padding: "16px 24px", borderBottom: "1px solid #E5E7EB" }}>
                    <label
                      style={{
                        display: "block",
                        fontWeight: 600,
                        marginBottom: "8px",
                        fontSize: "14px",
                        color: "#374151",
                      }}
                    >
                      Feedback do Professor
                    </label>
                    <textarea
                      value={professorFeedback}
                      onChange={(e) => {
                        setProfessorFeedback(e.target.value);
                        setFeedbackError(null);
                      }}
                      placeholder="Escreva aqui um comentário direcionado ao aluno sobre esta redação..."
                      maxLength={MAX_FEEDBACK_LENGTH}
                      disabled={isSavingFeedback}
                      style={{
                        width: "100%",
                        minHeight: "100px",
                        padding: "10px 12px",
                        borderRadius: "6px",
                        border: "1px solid #D1D5DB",
                        fontFamily: "inherit",
                        fontSize: "14px",
                        resize: "vertical",
                        boxSizing: "border-box",
                      }}
                    />
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginTop: "8px",
                        fontSize: "12px",
                        color: "#6B7280",
                      }}
                    >
                      <span>
                        {professorFeedback.length}/{MAX_FEEDBACK_LENGTH}
                        {feedbackSavedAt && !feedbackDirty && (
                          <span style={{ marginLeft: "12px", color: "#059669" }}>
                            Salvo em{" "}
                            {new Date(feedbackSavedAt).toLocaleString("pt-BR")}
                          </span>
                        )}
                      </span>
                      <button
                        onClick={handleSaveFeedback}
                        disabled={isSavingFeedback || !feedbackDirty}
                        style={{
                          padding: "6px 14px",
                          background: !feedbackDirty ? "#E5E7EB" : "#2E7BF3",
                          color: !feedbackDirty ? "#6B7280" : "white",
                          border: "none",
                          borderRadius: "6px",
                          cursor:
                            isSavingFeedback || !feedbackDirty
                              ? "not-allowed"
                              : "pointer",
                          fontWeight: 600,
                          fontSize: "13px",
                        }}
                      >
                        {isSavingFeedback ? "Salvando..." : "Salvar feedback"}
                      </button>
                    </div>
                    {feedbackError && (
                      <p
                        style={{
                          marginTop: "6px",
                          color: "#EF4444",
                          fontSize: "12px",
                        }}
                      >
                        {feedbackError}
                      </p>
                    )}
                  </div>

                  {/* Lista de competências */}
                  <div className={styles.criteria_container}>
                    {correctionData.competencies && Array.isArray(correctionData.competencies) ? (
                      correctionData.competencies.map((item, index) => {
                        // Define a cor com base na nota
                        let color: "red" | "blue" | "green";
                        if (item.grade <= 99) {
                          color = "red";
                        } else if (item.grade <= 150) {
                          color = "blue";
                        } else {
                          color = "green";
                        }
                        
                        return (
                          <Criteria
                            key={index}
                            title={item.competency}
                            score={item.grade}
                            total={200}
                            color={color}
                            feedback={item.justification}
                            isOpen={isDetailedView || openCriteria[index]}
                            onToggle={() => toggleCriteria(index)}
                          />
                        );
                      })
                    ) : (
                      <p style={{ padding: '15px', textAlign: 'center' }}>Nenhuma competência encontrada para esta redação.</p>
                    )}
                  </div>
                </div>
              ) : (
                // Visualização detalhada (semelhante ao study-plan)
                <div className={studyPlanStyles.studyPlanContainer} style={{ borderRadius: '0' }}>
                  {/* Nota e análise geral no topo */}
                  <div className={styles.score_section}>
                    <div className={styles.flex}>
                      <h2 className={styles.score_label}>NOTA</h2>
                      <div className={styles.gradeCard}>
                        <div className={styles.gradeValue}>
                          {Math.round(correctionData.overall_grade as number || 0)}
                          <span className={styles.gradeMax}>/1000</span>
                        </div>
                      </div>
                    </div>
                    <p className={styles.score_subtitle}>
                      {correctionData.detailed_analysis}
                    </p>
                  </div>

                  {/* Lista de Competências como botões */}
                  <div className={studyPlanStyles.competencyList}>
                    {correctionData.competencies?.map((comp, index) => {
                      const errorCount = comp.errors?.length || 0;
                      return (
                        <button
                          key={index}
                          className={`${studyPlanStyles.competencyButton} ${getErrorClass(errorCount)} ${
                            selectedCompetency === comp.competency ? studyPlanStyles.active : ""
                          }`}
                          onClick={() => handleCompetencyClick(comp.competency)}
                        >
                          {comp.competency} <span>({errorCount})</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className={studyPlanStyles.mainContent}>
                    {/* Seção de Erros */}
                    {selectedCompetency && (
                      <div className={studyPlanStyles.errorSection}>
                        <div className={studyPlanStyles.sectionHeader}>
                          <h3>Trecho em Foco</h3>
                        </div>

                        <div className={studyPlanStyles.errorCont}>
                          {/* Lista de erros para a competência selecionada */}
                          <div className={studyPlanStyles.errorList}>
                            {correctionData.competencies
                              ?.find((c) => c.competency === selectedCompetency)
                              ?.errors?.map((err, idx) => (
                                <div
                                  key={idx}
                                  className={`${studyPlanStyles.errorItem} ${
                                    selectedError === idx ? studyPlanStyles.selectedError : ""
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
                            <div className={studyPlanStyles.errorDetails}>
                              <p>
                                <strong className={studyPlanStyles.titleDetails}>Trecho em foco: </strong>
                                "
                                {
                                  correctionData.competencies
                                    ?.find((c) => c.competency === selectedCompetency)
                                    ?.errors[selectedError].snippet
                                }
                                "
                              </p>
                              <hr className={studyPlanStyles.line} />
                              <p>
                                <strong className={studyPlanStyles.titleDetails}>Tipo de erro:</strong>{" "}
                                {
                                  correctionData.competencies
                                    ?.find((c) => c.competency === selectedCompetency)
                                    ?.errors[selectedError].error_type
                                }
                              </p>
                              {correctionData.competencies
                                ?.find((c) => c.competency === selectedCompetency)
                                ?.errors[selectedError].explanation && (
                                <p>
                                  <strong className={studyPlanStyles.titleDetails}>Explicação:</strong>{" "}
                                  {
                                    correctionData.competencies
                                      ?.find((c) => c.competency === selectedCompetency)
                                      ?.errors[selectedError].explanation
                                  }
                                </p>
                              )}
                              <hr className={studyPlanStyles.line} />
                              <p>
                                <strong className={studyPlanStyles.titleDetails}>Correção:</strong>{" "}
                                {
                                  correctionData.competencies
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
                    <div className={studyPlanStyles.essaySection}>
                      <h3>Redação do Aluno</h3>
                      <div
                        ref={essayContentRef}
                        className={studyPlanStyles.essayContent}
                        dangerouslySetInnerHTML={{
                          __html: formatEssayWithParagraphs(highlightedEssayHTML || essayContent)
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center' }}>
              <p>Nenhum dado de correção encontrado.</p>
            </div>
          )}
        </div>

        <div className={styles.modalFooter}>
          {correctionData && !isDetailedView && (
            <button 
              className={styles.modalFeedbackButton}
              onClick={() => setIsDetailedView(true)}
            >
              Ver feedback detalhado
            </button>
          )}
          {correctionData && isDetailedView && (
            <button 
              className={styles.modalBackButton}
              onClick={() => setIsDetailedView(false)}
            >
              Voltar para correção
            </button>
          )}
          <button 
            className={styles.modalCancelButton} 
            onClick={onClose}
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
};

export default CorrecaoProfessorModal;