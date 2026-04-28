"use client";

import React, { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useRouter } from "next/navigation";
import styles from "./correcao-professor.module.css";

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
export default function CorrecaoProfessorModal({
  isOpen,
  onClose,
  studentId,
  essayId,
}: {
  isOpen: boolean;
  onClose: () => void;
  studentId: string;
  essayId: string;
}) {
  const router = useRouter();
  const [correctionData, setCorrectionData] = useState<CorrectionData | null>(null);
  const [openCriteria, setOpenCriteria] = useState<boolean[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && essayId) {
      fetchCorrectionData(essayId);
    }
  }, [isOpen, essayId]);

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
      
      // Atualiza o estado com os dados da correção
      setCorrectionData(result);
      
      // Inicializa o array de "aberto/fechado" para cada competência
      if (result.competencies && Array.isArray(result.competencies)) {
        setOpenCriteria(result.competencies.map(() => false));
      }
    } catch (error) {
      console.error("Erro ao buscar dados da correção:", error);
      setError("Não foi possível carregar os dados da correção. Tente novamente.");
    } finally {
      setIsLoading(false);
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

  // Se a modal não estiver aberta, não renderiza nada
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent} style={{ maxWidth: '800px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className={styles.modalHeader}>
          <h2>Correção da Redação</h2>
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
            <div className={styles.feedback_container} style={{ margin: '0', boxShadow: 'none', borderRadius: '0' }}>
              <div className={styles.score_section}>
                <div className={styles.flex}>
                  <h2 className={styles.score_label}>NOTA</h2>
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

              {/* Lista de competências */}
              <div className={styles.criteria_container}>
                {correctionData.competencies.map((item, index) => {
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
                      isOpen={openCriteria[index]}
                      onToggle={() => toggleCriteria(index)}
                    />
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center' }}>
              <p>Nenhum dado de correção encontrado.</p>
            </div>
          )}
        </div>

        <div className={styles.modalFooter}>
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
}