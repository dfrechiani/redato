"use client";

import { useState, useEffect } from "react";
import { LayoutGrid, FileText, BookOpen, PenTool, User2, Bell, Settings, LogOut, Download } from "lucide-react";
import Link from "next/link";
import styles from "./dashboard.module.css";

// Components
import { LineChart } from "./components/LineChart";
import { CompetencyChart } from "./components/CompentencyChart";
import Layout from "./components/Layout";

// 1. Interface para cada competência
export interface EssayCompetency {
  grade: number;
  detailed_analysis: string;
  justification: string;
}

// 2. Interface para os dados de cada redação
export interface EssayData {
  overall_grade: number;
  theme: string;
  competencies: {
    [competencyName: string]: EssayCompetency;
  };
}

// 3. Interface para os dados do dashboard
export interface DashboardData {
  total_essays: number;
  average_grade: number;
  competency_averages: {
    [competencyName: string]: number;
  };
  essays?: {
    [essayId: string]: EssayData;
  };
  // Outros campos, se necessário
}

export default function DashboardPage() {
  const [activeCompetency, setActiveCompetency] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);

  const colors = [
    "#2E7BF3", // Azul
    "#9FE870", // Verde
    "#9333EA", // Roxo
    "#84CC16", // Lima
    "#E5E7EB", // Cinza
  ];

  useEffect(() => {
    // Em uma página de debug, apenas para teste
    console.log("Firebase Config:", {
      apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
      authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
      projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
      storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
      appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    })
    // Se os dados já foram carregados, não refazer o fetch
    if (dashboardData !== null) return;
    if (typeof window === "undefined") return;

    const userId = localStorage.getItem("user_id");
    console.log("User ID recuperado no Dashboard:", userId);

    if (!userId) {
      console.error("Usuário não autenticado!");
      return;
    }

    const fetchDashboardData = async () => {
      try {
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
        // Se não houver dados, inicializa com valores vazios
        if (!data || !data.total_essays) {
          setDashboardData({
            total_essays: 0,
            average_grade: 0,
            competency_averages: {},
            essays: {}
          });
        } else {
          // Log para depuração - verificar a estrutura dos dados das redações
          console.log("Dados recebidos do dashboard:", data);
          if (data.essays) {
            console.log("Estrutura da primeira redação:", Object.values(data.essays)[0]);
            // Verifica se o campo graded_at existe
            const firstEssay = Object.values(data.essays)[0] as any;
            if (firstEssay) {
              console.log("Tem graded_at?", 'graded_at' in firstEssay);
              console.log("Valor de graded_at:", firstEssay.graded_at);
            }
          }
          
          setDashboardData(data);
        }
      } catch (error) {
        console.error(error);
        // Em caso de erro, inicializa com valores vazios
        setDashboardData({
          total_essays: 0,
          average_grade: 0,
          competency_averages: {},
          essays: {}
        });
      }
    };

    fetchDashboardData();
  }, [dashboardData]);

  // Enquanto os dados não forem carregados, exibe uma tela de loading personalizada
  if (dashboardData === null) {
    return (
      <Layout role="aluno" background="#fff">
        <div className={styles.loadingContainer}>
          <img src="/icone-preto.png" alt="Loading" className={styles.loadingLogo} />
        </div>
      </Layout>
    );
  }

  // Verifica se não há dados para mostrar
  const hasNoData = !dashboardData.total_essays || dashboardData.total_essays === 0;

  return (
    <Layout role="aluno" background="#f8f9fb">
      <div className={styles.container}>
        {/* Main Content */}
        <main className={styles.mainContent}>
          {/* Grade Card */}
          <div className={styles.gradeCard}>
            <span className={styles.gradeLabel}>Nota Média</span>
            <div className={styles.gradeValue}>
              {hasNoData ? (
                <span className={styles.noDataMessage}>-</span>
              ) : (
                <>
                  {Math.round(dashboardData.average_grade || 0)}
                  <span className={styles.gradeMax}>/1000</span>
                </>
              )}
            </div>
          </div>

          {/* Evolution Chart */}
          <div className={styles.chartCard}>
            <span className={styles.gradeLabel}>Sua evolução</span>
            <div className={styles.chartContainer}>
              {hasNoData ? (
                <div className={styles.noDataContainer}>
                  <p className={styles.noDataMessage}>Envie sua primeira redação para desbloquear essa função</p>
                </div>
              ) : (
                <LineChart dashboardData={dashboardData} />
              )}
            </div>
          </div>

          {/* Competências */}
          <div className={styles.competenciesCard}>
            <span className={styles.gradeLabel}>Competências</span>
            <div className={styles.competenciesContent}>
              {hasNoData ? (
                <div className={styles.noDataContainer}>
                  <p className={styles.noDataMessage}>Envie sua primeira redação para desbloquear essa função</p>
                </div>
              ) : (
                dashboardData && dashboardData.competency_averages ? (
                  <CompetencyChart
                    data={dashboardData.competency_averages}
                    activeIndex={activeCompetency}
                    setActiveIndex={setActiveCompetency}
                  />
                ) : (
                  <p>Carregando dados...</p>
                )
              )}
            </div>
          </div>
        </main>

        {/* Right Panel */}
        <aside className={styles.rightPanel}>
          {/* Redações */}
          <div className={styles.essaysCard}>
            <span className={styles.gradeLabel}>Redações</span>
            <div className={styles.essaysList}>
              {hasNoData ? (
                <div className={styles.noDataContainer}>
                  <p className={styles.noDataMessage}>Envie sua primeira redação para desbloquear essa função</p>
                </div>
              ) : (
                dashboardData?.essays ? (
                  <>
                    {Object.entries(dashboardData.essays)
                      // Ordenar as redações da mais antiga para a mais recente
                      .sort(([, essayA], [, essayB]) => {
                        const dateA = (essayA as any).graded_at ? new Date((essayA as any).graded_at) : new Date(0);
                        const dateB = (essayB as any).graded_at ? new Date((essayB as any).graded_at) : new Date(0);
                        return dateA.getTime() - dateB.getTime();
                      })
                      .slice(0, showAll ? Object.keys(dashboardData.essays).length : 4)
                      .map(([id, essay], index) => {
                        // Formatar a data da redação
                        const essayDate = (essay as any).graded_at 
                          ? new Date((essay as any).graded_at)
                          : null;
                        
                        const formattedDate = essayDate 
                          ? `${essayDate.getDate().toString().padStart(2, '0')}/${(essayDate.getMonth() + 1).toString().padStart(2, '0')}`
                          : "";
                        
                        return (
                          <div key={id} className={styles.essayItem}>
                            <div className={styles.essayInfo}>
                              <span 
                                className={`${styles.essayId} ${styles.essayColor}`} 
                                style={{ backgroundColor: colors[index % colors.length] }}
                              >
                                {String(index + 1).padStart(2, "0")}
                              </span>
                              <div className={styles.essayDetails}>
                                <span className={styles.essayTitle}>
                                  {(essay as EssayData).theme
                                    ? (essay as EssayData).theme.length > 25
                                      ? `${(essay as EssayData).theme.slice(0, 25)}...`
                                      : (essay as EssayData).theme
                                    : "Sem tema"}
                                </span>
                                {formattedDate && (
                                  <span className={styles.essayDate}>
                                    {formattedDate}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className={styles.essayScore}>
                              <span>{(essay as EssayData).overall_grade}</span>
                            </div>
                          </div>
                        );
                      })}
                  </>
                ) : (
                  <p>Carregando redações...</p>
                )
              )}
            </div>
            {!hasNoData && dashboardData?.essays && Object.keys(dashboardData.essays).length > 4 && (
              <button className={styles.showMoreButton} onClick={() => setShowAll(!showAll)}>
                {showAll ? "Mostrar menos ↑" : "Mostrar mais ↓"}
              </button>
            )}
          </div>
          {/* Study Plan
          <div className={styles.studyPlanCard}>
            <span className={styles.gradeLabel}>Plano de Estudo</span>
            <div className={styles.studyPlanList}>
              <div className={styles.studyPlanItem}>
                <div className={styles.studyPlanDot} />
                <span>Exercício 01: Domínio da Norma Culta</span>
              </div>
              <div className={styles.studyPlanItem}>
                <div className={styles.studyPlanDot} />
                <span>Exercício 02: Seleção e Organização das Informações</span>
              </div>
              <div className={styles.studyPlanItem}>
                <div className={styles.studyPlanDot} />
                <span>Exercício 03: Elaboração de Proposta de Intervenção</span>
              </div>
            </div>
            <div className={styles.containerButton}>
              <button className={styles.exerciseButton}>Realizar Exercícios</button>
            </div>
          </div> */}
          <Link href="/select">
            <button className={styles.submitEssayButton}>
              <PenTool size={20} /> ENVIAR NOVA REDAÇÃO
            </button>
          </Link>
        </aside>
      </div>
    </Layout>
  );
}
