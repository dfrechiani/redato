"use client"

import { useMemo, useState } from "react"
import styles from "./CompetencyChart.module.css"

interface CompetencyChartProps {
  data: { [competencyName: string]: number }
  activeIndex?: number
  setActiveIndex?: (index: number) => void
}

// Mapeamento das competências com suas descrições
const competencyDescriptions = {
  "Domínio da Norma Culta": "Avalia o uso correto da língua portuguesa, incluindo ortografia, acentuação e pontuação.",
  "Compreensão do Tema": "Analisa a capacidade de entender e desenvolver o tema proposto de forma adequada.",
  "Seleção e Organização das Informações": "Verifica a organização e seleção adequada dos argumentos e informações.",
  "Conhecimento dos Mecanismos Linguísticos": "Avalia o uso de recursos linguísticos para construir a argumentação.",
  "Proposta de Intervenção": "Analisa a capacidade de propor soluções para o problema apresentado."
}

export function CompetencyChart({ data, activeIndex, setActiveIndex }: CompetencyChartProps) {
  const [highlightedCompetency, setHighlightedCompetency] = useState<string | null>(null);

  const colors = [
    "#4361EE", // Domínio da Norma Culta (Azul)
    "#3ADAA8", // Compreensão do Tema (Verde)
    "#0096FF", // Seleção e Organização (Azul Claro)
    "#C5F364", // Mecanismos Linguísticos (Verde Limão)
    "#A0AEC0", // Proposta de Intervenção (Cinza)
  ];

  const competencies = useMemo(() => {
    return Object.entries(data).map(([name, value], index) => ({
      id: index + 1,
      name: name,
      value: value,
      color: colors[index % colors.length]
    }));
  }, [data]);

  const handleLegendClick = (competencyName: string) => {
    setHighlightedCompetency(highlightedCompetency === competencyName ? null : competencyName);
  };

  return (
    <div className={styles.competencyCard}>
      <div className={styles.competencyChart}>
        <div className={styles.competencyChartContent}>
          <div className={styles.competencyGridLines}>
            <div className={styles.verticalLine} style={{ left: "0%" }}></div>
            <div className={styles.verticalLine} style={{ left: "25%" }}></div>
            <div className={styles.verticalLine} style={{ left: "50%" }}></div>
            <div className={styles.verticalLine} style={{ left: "75%" }}></div>
            <div className={styles.verticalLine} style={{ left: "100%" }}></div>
          </div>
          {competencies.map((competency) => (
            <div key={competency.id} className={styles.competencyItem}>
              <div className={styles.competencyNumber}>{competency.id}</div>
              <div className={`${styles.competencyBarContainer} ${highlightedCompetency === competency.name ? styles.highlighted : ''}`}>
                <div
                  className={styles.competencyBar}
                  style={{
                    width: `${Math.max(0, Math.min(100, (competency.value / 200) * 100))}%`,
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

      <div className={styles.legend}>
        <div className={styles.legendItems}>
          {competencies.map((competency) => (
            <div 
              key={competency.id} 
              className={styles.legendItem}
              onClick={() => handleLegendClick(competency.name)}
            >
              <div className={styles.legendColor} style={{ backgroundColor: competency.color }}></div>
              <div className={styles.legendText}>{competency.name}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
