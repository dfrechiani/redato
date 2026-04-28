"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Layout from "../dashboard/components/Layout";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import styles from "./correcao.module.css";
import Link from "next/link";

interface Competency {
  competency: string;
  grade: number;
  justification: string;
  errors: any[];
}

interface CorrectionData {
  overall_grade: number;       // Nota geral (ex.: 768)
  detailed_analysis: string;   // Ex.: "Melhor resultado até agora!"
  competencies: Competency[];  // Lista de competências
  essay_id?: string;           // ID da redação (opcional)
}

// Interface para os dados de cada redação (reaproveitando do dashboard)
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

// Modal de seleção de redações
const EssaySelectionModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  essays: { [id: string]: EssayData } | undefined;
  onSelect: (id: string) => void;
}> = ({ isOpen, onClose, essays, onSelect }) => {
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
          <h2>Selecione uma redação para visualizar</h2>
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

export default function CorrecaoPage() {
  const router = useRouter();
  const [correctionData, setCorrectionData] = useState<CorrectionData | null>(null);
  const [openCriteria, setOpenCriteria] = useState<boolean[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [professorFeedback, setProfessorFeedback] =
    useState<ProfessorFeedback | null>(null);

  useEffect(() => {
    // Verifica se há dados de correção no localStorage
    const storedData = localStorage.getItem("correctionData");

    if (storedData) {
      try {
        const parsed = JSON.parse(storedData);
        // Se os dados vierem dentro de "data", pega de lá; se não, pega do próprio objeto
        const correction: CorrectionData = parsed.data ? parsed.data : parsed;
        setCorrectionData(correction);

        // Inicializa o array de "aberto/fechado" para cada competência
        if (correction.competencies && Array.isArray(correction.competencies)) {
          setOpenCriteria(correction.competencies.map(() => false));
        }
        setIsLoading(false);
      } catch (error) {
        console.error("Erro ao parsear os dados da correção:", error);
        setIsLoading(false);
      }
    } else {
      // Se não há dados no localStorage, busca os dados do dashboard
      fetchDashboardData();
    }
  }, []);

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

  // Função para buscar dados do dashboard
  // Função para buscar dados do dashboard
const fetchDashboardData = async () => {
  try {
    setIsLoading(true);
    const userId = localStorage.getItem("user_id");
    
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

  // Função para selecionar redação diretamente do dashboard
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
      
      // Salva no localStorage
      localStorage.setItem("correctionData", JSON.stringify(correctionData));
      
      // Atualiza o estado
      setCorrectionData(correctionData);
      
      // Inicializa o array de "aberto/fechado" para cada competência
      if (correctionData.competencies && Array.isArray(correctionData.competencies)) {
        setOpenCriteria(correctionData.competencies.map(() => false));
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
        
        localStorage.setItem("correctionData", JSON.stringify(fallbackCorrection));
        setCorrectionData(fallbackCorrection);
        setOpenCriteria(fallbackCorrection.competencies.map(() => false));
      } else {
        alert("Não foi possível carregar os dados desta redação");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <Layout background="url('/bg-redato.png') no-repeat center center fixed">
        <div className={styles.loading_container}>
          <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} />
        </div>
      </Layout>
    );
  }

  // Se não há correção selecionada e não tem modal aberta
  if (!correctionData && !isModalOpen) {
    return (
      <Layout background="url('/bg-redato.png') no-repeat center center fixed">
        <div className={styles.feedback_container}>
          <div className={styles.no_correction}>
            <h2>Nenhuma correção selecionada</h2>
            <button 
              className={styles.select_essay_button}
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
        </div>
      </Layout>
    );
  }

  // Se tem dados de correção
  if (correctionData && Array.isArray(correctionData.competencies)) {
    // Cada competência vale 200 pontos
    const totalScore = correctionData.competencies.length * 200;

    // Mapeia os dados para o componente Criteria, definindo a cor conforme o score:
    // até 99 → vermelho, até 150 → azul, até 200 → verde.
    const criteriaData = correctionData.competencies.map((item) => {
      let color: "red" | "blue" | "green";
      if (item.grade <= 99) {
        color = "red";
      } else if (item.grade <= 150) {
        color = "blue";
      } else {
        color = "green";
      }
      return {
        title: item.competency,
        score: item.grade,
        total: 200,
        color: color,
        feedback: item.justification,
        progress: "", // Se tiver alguma informação extra para mostrar
      };
    });

    // Função para abrir/fechar cada collapsible
    const toggleCriteria = (index: number) => {
      setOpenCriteria((prev) => {
        const newState = [...prev];
        newState[index] = !newState[index];
        return newState;
      });
    };

    return (
      <Layout background="url('/bg-redato.png') no-repeat center center fixed">
        <EssaySelectionModal 
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          essays={dashboardData?.essays}
          onSelect={handleEssaySelection}
        />

        <div className={styles.feedback_container}>
          <div className={styles.score_section}>
            <div className={styles.flex}>
              <h2 className={styles.score_label}>SUA <br />NOTA:</h2>
              <div className={styles.gradeCard}>
                <div className={styles.gradeValue}>
                  {Math.round(correctionData.overall_grade || 0)}
                  <span className={styles.gradeMax}>/1000</span>
                </div>
              </div>
            </div>
            <p className={styles.score_subtitle}>
              {correctionData.detailed_analysis}
            </p>
          </div>

          {professorFeedback && (
            <div
              style={{
                margin: "16px 24px",
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

          {/* Lista de competências */}
          <div className={styles.criteria_container}>
            {criteriaData.map((item, index) => (
              <Criteria
                key={index}
                {...item}
                isOpen={openCriteria[index]}
                color={item.color}
                onToggle={() => toggleCriteria(index)}
              />
            ))}
          </div>
        </div>

        <div className={styles.btnContainer || styles.action_buttons}>
        <button 
            className={styles.select_another_button}
            onClick={() => {
              // Busca os dados novamente antes de abrir a modal
              fetchDashboardData().then(() => {
                setIsModalOpen(true);
              });
            }}
          >
            SELECIONAR OUTRA REDAÇÃO
          </button>
          <Link href="/study-plan">
            <button className={styles.exerciseButton}>
              VER FEEDBACK DETALHADO
            </button>
          </Link>
        </div>
      </Layout>
    );
  }

  // Renderiza a modal caso esteja aberta
  return (
    <Layout background="url('/bg-redato.png') no-repeat center center fixed">
      <EssaySelectionModal 
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          router.push('/dashboard');
        }}
        essays={dashboardData?.essays}
        onSelect={handleEssaySelection}
      />
      
      <div className={styles.feedback_container}>
        <div className={styles.no_correction}>
          <h2>Selecione uma redação para visualizar a correção</h2>
        </div>
      </div>
    </Layout>
  );
}