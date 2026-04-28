"use client";

import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  ScriptableContext,
  Scale,
  Tick,
} from "chart.js";
import { DashboardData, EssayData } from "../page";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler
);

interface LineChartProps {
  dashboardData: DashboardData | null;
}

export function LineChart({ dashboardData }: LineChartProps) {
  // Array para armazenar as notas de cada redação.
  const essayGrades: number[] = [];
  // Array para armazenar as datas das redações
  const essayDates: string[] = [];
  // Data original da redação (sem os pontos extras)
  let originalDate = "";

  if (dashboardData && dashboardData.essays) {
    // Converte as redações em array
    let essaysArray = Object.values(dashboardData.essays) as EssayData[];

    // Ordena as redações pela data do graded_at
    essaysArray.sort((a: any, b: any) => {
      if (a.graded_at && b.graded_at) {
        return new Date(a.graded_at).getTime() - new Date(b.graded_at).getTime();
      }
      return 0;
    });

    // Pega as 15 últimas redações (se houver menos, pega todas)
    const last15Essays = essaysArray.slice(-15);

    last15Essays.forEach((ed: any, index) => {
      if (ed && typeof ed.overall_grade === "number") {
        essayGrades.push(ed.overall_grade);
        
        // Formata a data para exibição (DD/MM)
        if (ed.graded_at) {
          const date = new Date(ed.graded_at);
          const formattedDate = `${date.getDate().toString().padStart(2, '0')}/${(date.getMonth() + 1).toString().padStart(2, '0')}`;
          essayDates.push(formattedDate);
          
          // Se for a primeira/única redação, guardar a data original
          if (essayGrades.length === 1) {
            originalDate = formattedDate;
          }
          
          console.log(`Redação ${index} com data: ${formattedDate} de ${ed.graded_at}`);
        } else {
          // Se não tiver data, usar uma data padrão (hoje)
          const today = new Date();
          const defaultDate = `${today.getDate().toString().padStart(2, '0')}/${(today.getMonth() + 1).toString().padStart(2, '0')}`;
          essayDates.push(defaultDate);
          
          // Se for a primeira/única redação, guardar a data padrão
          if (essayGrades.length === 1) {
            originalDate = defaultDate;
          }
          
          console.log(`Redação ${index} sem data, usando data padrão: ${defaultDate}`);
        }
      }
    });
    
    // Log para debug
    console.log("Grades:", essayGrades);
    console.log("Dates:", essayDates);
  }

  // Se houver apenas uma redação, adicionamos um ponto inicial com nota 0
  if (essayGrades.length === 1) {
    const grade = essayGrades[0];
    // Adiciona um valor 0 no início para criar uma linha ascendente
    essayGrades.unshift(0);
    // Mantém o mesmo valor no fim se quiser expandir a linha
    essayGrades.push(grade);
    
    // Adiciona data para os pontos extras (isso fará com que apareçam as datas embaixo de todos os pontos)
    // Primeiro ponto - mesma data, precedido de "início"
    essayDates.unshift(`Início`);
    // Último ponto - mesma data que o ponto do meio
    essayDates.push(originalDate);
    
    // Debug - vamos imprimir as datas para verificar
    console.log("Essay dates após ajuste:", essayDates);
    console.log("Original date:", originalDate);
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      tooltip: {
        backgroundColor: "rgba(0, 0, 0, 0.9)",
        titleColor: "#fff",
        bodyColor: "#fff",
        bodyFont: {
          size: 22 as const,
          weight: "bold" as const,
        },
        titleFont: {
          size: 14 as const,
          weight: "bold" as const,
        },
        padding: 12,
        displayColors: false,
        callbacks: {
          label: (tooltipItem: any) => `Nota: ${tooltipItem.parsed.y}`,
          title: (tooltipItems: any) => {
            const index = tooltipItems[0].dataIndex;
            return essayDates[index] ? `Data: ${essayDates[index]}` : '';
          }
        },
      },
      legend: {
        display: false,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { 
          // Exibe as datas no eixo X para todos os pontos
          callback: function(this: Scale<any>, value: any, index: number) {
            return essayDates[index] || "";
          },
          font: {
            size: 11,
            weight: 'bold'
          },
          color: '#7d8390',
          padding: 10,
          // Rotaciona o texto para evitar sobreposição
          maxRotation: 0,
          minRotation: 0,
        },
      },
      y: {
        min: 0,
        max: 1020,
        grid: { display: false },
        ticks: {
          autoSkip: false,
          callback: (value: any) => (value !== undefined ? value.toString() : ""),
        },
        afterBuildTicks: (scale: any) => {
          scale.ticks = [
            { value: 0 },
            { value: 200 },
            { value: 400 },
            { value: 600 },
            { value: 800 },
            { value: 1000 },
          ];
        },
      },
    },
    elements: {
      line: {
        tension: 0.5,
        borderWidth: 3,
      },
      point: {
        // Pontos menores e mais discretos
        radius: 3,
        hoverRadius: 8, // Aumenta quando o mouse passar por cima
        hitRadius: 15,  // Área de detecção do mouse
        // Adiciona borda para destacar os pontos
        borderWidth: 1.5, 
        borderColor: '#fff',
        backgroundColor: 'rgb(97, 160, 255)',
      },
    },
  } as const;

  const data = {
    labels: essayDates,
    datasets: [
      {
        fill: true,
        data: essayGrades,
        borderColor: "rgb(97, 160, 255)",
        backgroundColor: (context: ScriptableContext<"line">) => {
          const { ctx, chartArea } = context.chart;
          if (!chartArea) return undefined;
          return createGradient(ctx, chartArea);
        },
        borderWidth: 3, // Reduzido para ficar mais fino e elegante
        spanGaps: true,  // Permite que a linha pule sobre valores nulos
        pointBackgroundColor: 'rgb(97, 160, 255)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: 'rgb(67, 130, 255)', // Cor um pouco mais escura ao passar o mouse
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2, // Borda mais grossa ao passar o mouse
      },
    ],
  };

  function createGradient(
    ctx: CanvasRenderingContext2D,
    chartArea: { top: number; bottom: number }
  ): CanvasGradient {
    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, "rgba(96, 202, 255, 0.89)");
    gradient.addColorStop(1, "rgba(96, 202, 255, 0.1)");
    return gradient;
  }

  return <Line options={options} data={data} />;
}
