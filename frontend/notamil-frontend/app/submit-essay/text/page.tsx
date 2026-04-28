"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Layout from "../../dashboard/components/Layout";
import styles from "../submit-essay.module.css";
import { useRouter } from "next/navigation";
import { Info, ChevronDown } from "lucide-react";

type JobStatus = "pending" | "processing" | "completed" | "failed" | "not_found";

interface CorrectionResponse {
  request_id: string;
  status?: JobStatus;
  data?: {
    overall_grade: number;
    detailed_analysis: string;
    competencies: any[];
    essay_id?: string;
  } | null;
  error?: string | null;
  preview_feedback?: string | null;
}

interface SubmitResponse {
  request_id?: string;
  essay_id?: string;
  status?: JobStatus;
  error?: string;
  detail?: string;
}

const POLLING_INTERVAL_MS = 3000;
const MAX_POLLING_MS = 10 * 60 * 1000; // 10 min hard cap
const MAX_POLLING_ATTEMPTS = Math.ceil(MAX_POLLING_MS / POLLING_INTERVAL_MS);
const OCR_ACCURACY_WARNING_THRESHOLD = 0.8;

interface ThemeOption {
  id: string;
  name: string;
  description: string;
  class_id: string;
}

interface Segment {
  type: 'text' | 'uncertain';
  content: string;
  id: string;
  originalContent?: string;
  edited?: boolean;
}

interface HighlightedTextProps {
  text: string;
  onChange: (newText: string) => void;
}

interface BaseSegment {
  content: string;
  id: string;
}

interface TextSegment extends BaseSegment {
  type: "text";
}

interface UncertainSegment extends BaseSegment {
  type: "uncertain";
  originalContent: string;
  edited: boolean;
}

const HighlightedText: React.FC<HighlightedTextProps> = ({ text, onChange }) => {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);

  const parseText = (content: string): Segment[] => {
    const parts: Segment[] = [];
    let currentIndex = 0;
    // Atualizamos a regex para capturar HIGH, MEDIUM ou LOW e o conteúdo entre as tags
    const regex = /<uncertain confidence='(HIGH|MEDIUM|LOW)'>(.*?)<\/uncertain>/g;
    let match: RegExpExecArray | null;
  
    while ((match = regex.exec(content)) !== null) {
      if (match.index > currentIndex) {
        parts.push({
          type: "text",
          content: content.slice(currentIndex, match.index),
          id: `text-${currentIndex}`,
        });
      }
      // match[1] contém o nível de confiança e match[2] o conteúdo
      parts.push({
        type: "uncertain",
        content: match[2],
        originalContent: match[2],
        id: `uncertain-${match.index}`,
        edited: false,
        // Caso queira armazenar o nível de confiança, você pode adicionar essa propriedade:
        confidence: match[1],
      } as any); // 'as any' se a interface Segment não possuir a propriedade confidence
      currentIndex = match.index + match[0].length;
    }
    if (currentIndex < content.length) {
      parts.push({
        type: "text",
        content: content.slice(currentIndex),
        id: `text-${currentIndex}`,
      });
    }
    return parts;
  };
  

  const concatSegments = (segs: Segment[]): string =>
    segs
      .map((segment) =>
        segment.type === "uncertain"
          ? `<uncertain confidence='HIGH'>${segment.content}</uncertain>`
          : segment.content
      )
      .join("");

  useEffect(() => {
    // Inicializa os segmentos se ainda não foram definidos
    if (segments.length === 0) {
      setSegments(parseText(text));
    } else {
      const currentText = concatSegments(segments);
      if (currentText !== text) {
        // Se o texto foi alterado externamente (ex.: novo OCR), refaz o parse
        setSegments(parseText(text));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const handleWordClick = (id: string): void => {
    // Marca o segmento como editado imediatamente ao clicar
    setSegments((prevSegments) =>
      prevSegments.map((segment) =>
        segment.id === id ? { ...segment, edited: true } : segment
      )
    );
    setEditingId(id);
  };

  const handleWordEdit = (id: string, newValue: string): void => {
    const newSegments = segments.map((segment) => {
      if (segment.id === id) {
        return {
          ...segment,
          content: newValue,
          edited: true,
        };
      }
      return segment;
    });
    setSegments(newSegments);

    const newText = concatSegments(newSegments);
    onChange(newText);
  };

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>,
    id: string
  ): void => {
    if (e.key === "Enter") {
      e.preventDefault();
      setEditingId(null);
    }
  };

  const handleBlur = (): void => {
    setEditingId(null);
  };

  return (
    <div className={styles.highlightedText}>
      {segments.map((segment) => {
        if (segment.type === "uncertain") {
          if (editingId === segment.id) {
            return (
              <input
                key={segment.id}
                type="text"
                value={segment.content}
                onChange={(e) => handleWordEdit(segment.id, e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, segment.id)}
                onBlur={handleBlur}
                className={styles.uncertainWordInput}
                autoFocus
              />
            );
          }
          return (
            <span
              key={segment.id}
              className={`${styles.uncertainWord} ${
                segment.edited ? styles.edited : ""
              }`}
              onClick={() => handleWordClick(segment.id)}
              style={{
                cursor: "pointer",
                backgroundColor: segment.edited ? "#4CAF50" : "#FF5252",
                color: "white",
                padding: "4px",
                borderRadius: "3px",
              }}
            >
              {segment.content}
            </span>
          );
        }
        return <span key={segment.id}>{segment.content}</span>;
      })}
    </div>
  );
};

export default function SubmitEssayText() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [theme, setTheme] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [modalMessage, setModalMessage] = useState("Estamos processando sua redação...");
  const [showButtons, setShowButtons] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Sua criatividade está brilhando!");
  const [loadingThemes, setLoadingThemes] = useState(false);
  const [themes, setThemes] = useState<ThemeOption[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState("");
  const [showThemeDescription, setShowThemeDescription] = useState(false);
  const [themeDescriptionToShow, setThemeDescriptionToShow] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [ocrAccuracy, setOcrAccuracy] = useState<number | null>(null);
  const [ocrRequestId, setOcrRequestId] = useState<string | null>(null);
  const [previewFeedback, setPreviewFeedback] = useState<string>("");
  const [displayedPreview, setDisplayedPreview] = useState<string>("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  const classId = typeof window !== "undefined" ? localStorage.getItem("class_id") : null;

  useEffect(() => {
    // Carregar os temas disponíveis para a turma
    const fetchThemes = async () => {
      if (!classId) {
        console.error("Nenhum ID de turma encontrado");
        setLoadingThemes(false);
        return;
      }
      
      setLoadingThemes(true);
      try {
        const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/themes?class_id=${classId}`;
        console.log("Fazendo requisição para:", url);
        
        const response = await fetch(url);
        
        if (!response.ok) {
          console.error("Erro na resposta:", response.status, response.statusText);
          throw new Error(`Erro ao carregar temas: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("Dados recebidos da API:", data);
        
        if (data && data.data && Array.isArray(data.data)) {
          console.log("Temas encontrados:", data.data.length);
          setThemes(data.data);
        } else {
          console.warn("Formato de resposta inesperado:", data);
        }
      } catch (error) {
        console.error("Erro ao buscar temas:", error);
      } finally {
        setLoadingThemes(false);
      }
    };
    
    fetchThemes();
  }, [classId]);

  // Typewriter effect for the preview feedback. Reveals characters one by
  // one so the card fills in smoothly instead of flooding with a big blob of
  // text when each 3s poll lands.
  useEffect(() => {
    const cleanTarget = (previewFeedback || "")
      .replace(/^\*+[^*]+\*+\s*/, "")
      .trim();
    if (!cleanTarget) {
      setDisplayedPreview("");
      return;
    }

    let raf: number | null = null;
    let cancelled = false;
    let lastStep = 0;

    const tick = (now: number) => {
      if (cancelled) return;
      // Reveal ~1 char per 18ms ≈ 55 chars/s — fluid but readable.
      if (now - lastStep >= 18) {
        lastStep = now;
        setDisplayedPreview((prev) => {
          if (prev.length >= cleanTarget.length) return prev;
          return cleanTarget.slice(0, prev.length + 1);
        });
      }
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      if (raf !== null) cancelAnimationFrame(raf);
    };
  }, [previewFeedback]);

  useEffect(() => {
    const preFillTheme = localStorage.getItem("ocrPreFillTheme");
    const preFillContent = localStorage.getItem("ocrPreFillContent");
    if (preFillTheme) setTitle(preFillTheme);
    if (preFillContent) setContent(preFillContent);

    const storedAccuracy = localStorage.getItem("ocrAccuracy");
    if (storedAccuracy !== null) {
      const parsed = parseFloat(storedAccuracy);
      if (!Number.isNaN(parsed)) {
        setOcrAccuracy(parsed);
      }
    }

    const storedOcrRequestId = localStorage.getItem("ocrRequestId");
    if (storedOcrRequestId) {
      setOcrRequestId(storedOcrRequestId);
    }
  }, []);

  useEffect(() => {
    const messages = [
      "Sua criatividade está brilhando!",
      "Estamos olhando todos os detalhes!",
      "Falta só mais um minutinho!",
      "Fique de olho!"
    ];
    let currentIndex = 0;

    const intervalId = setInterval(() => {
      currentIndex = (currentIndex + 1) % messages.length;
      setLoadingMessage(messages[currentIndex]);
    }, 10000);

    return () => clearInterval(intervalId);
  }, []);

  const handleContentChange = useCallback((newContent: string) => {
    setTimeout(() => {
      setContent(newContent);
    }, 0);
  }, []);

  // Função para fechar o dropdown ao clicar fora dele
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleThemeSelect = (themeId: string, themeName: string = "") => {
    setSelectedThemeId(themeId);
    setIsDropdownOpen(false);
    
    // Se for "tema-livre", limpa o tema para o usuário digitar
    if (themeId === "tema-livre") {
      setTheme("");
      return;
    }
    
    // Usando o nome do tema passado ou buscando do array
    if (themeName) {
      setTheme(themeName);
    } else {
      // Encontra o tema selecionado e atualiza o valor do tema
      const selectedTheme = themes.find(t => t.id === themeId);
      if (selectedTheme) {
        setTheme(selectedTheme.name);
      }
    }
  };

  const handleShowThemeDescription = (themeId: string) => {
    // Se "tema-livre" foi selecionado
    if (themeId === "tema-livre") {
      setThemeDescriptionToShow("Crie uma redação com tema livre de sua escolha.");
      setShowThemeDescription(true);
      return;
    }
    
    // Encontra o tema e mostra sua descrição
    const selectedTheme = themes.find(t => t.id === themeId);
    if (selectedTheme) {
      setThemeDescriptionToShow(
        selectedTheme.description || 
        `O professor não adicionou uma descrição para este tema. Crie uma redação com base no tema: ${selectedTheme.name}`
      );
      setShowThemeDescription(true);
    }
  };

  const handleTextSubmit = async () => {
    setLoading(true);
    setShowModal(true);
    setModalMessage("Enviando redação...");
    setShowButtons(false);
    if (!userId) {
      setModalMessage("Erro: Usuário não autenticado!");
      setLoading(false);
      setShowButtons(true);
      return;
    }
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          theme: theme,
          content: content,
          ocr_id: ocrRequestId || "text",
          theme_id: selectedThemeId !== "tema-livre" ? selectedThemeId : undefined
        }),
      });
      const data: SubmitResponse = await response.json();
      if (!response.ok || data.status === "failed") {
        const message =
          data.error || data.detail || "Erro ao enviar redação. Tente novamente.";
        throw new Error(message);
      }
      const requestId = data.request_id || data.essay_id;
      if (!requestId) {
        throw new Error("O servidor não retornou um identificador da redação.");
      }
      setCurrentRequestId(requestId);
      setModalMessage("Redação enviada! Iniciando correção...");
    } catch (error: any) {
      console.error("Erro ao enviar redação:", error);
      setModalMessage(`Erro: ${error.message}`);
      setLoading(false);
      setShowButtons(true);
    }
  };

  useEffect(() => {
    if (!currentRequestId) return;
    let cancelled = false;
    let attempts = 0;

    const handleCompleted = (payload: CorrectionResponse) => {
      if (!payload.data) return false;
      const hasCompetencies =
        Array.isArray(payload.data.competencies) &&
        payload.data.competencies.length > 0;
      if (!hasCompetencies) return false;
      if (!payload.data.essay_id) {
        payload.data.essay_id = currentRequestId;
      }
      localStorage.setItem("ocrPreFillTheme", String(payload.data.overall_grade));
      localStorage.setItem("ocrPreFillContent", payload.data.detailed_analysis);
      localStorage.setItem("correctionData", JSON.stringify(payload.data));
      setModalMessage("Redação corrigida!");
      setShowButtons(true);
      setLoading(false);
      return true;
    };

    const poll = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/result/essay/${currentRequestId}`
        );
        const data: CorrectionResponse = await response.json();

        if (response.status === 422 || data.status === "failed") {
          cancelled = true;
          setModalMessage(
            `Erro: ${data.error || "Não foi possível corrigir a redação."}`
          );
          setShowButtons(true);
          setLoading(false);
          return;
        }

        if (response.ok && data.status === "completed" && handleCompleted(data)) {
          cancelled = true;
          return;
        }

        if (attempts >= MAX_POLLING_ATTEMPTS) {
          cancelled = true;
          setModalMessage(
            "Erro: A correção está demorando mais do que o esperado. Tente novamente em alguns minutos."
          );
          setShowButtons(true);
          setLoading(false);
          return;
        }

        if (typeof data.preview_feedback === "string" && data.preview_feedback !== previewFeedback) {
          setPreviewFeedback(data.preview_feedback);
        }

        setModalMessage("Ainda processando sua redação, por favor aguarde...");
      } catch (err) {
        console.error("Erro ao consultar resultado:", err);
        if (attempts >= MAX_POLLING_ATTEMPTS) {
          cancelled = true;
          setModalMessage(
            "Erro: Não foi possível obter o resultado. Verifique sua conexão e tente novamente."
          );
          setShowButtons(true);
          setLoading(false);
        }
      }
    };

    const intervalId = setInterval(poll, POLLING_INTERVAL_MS);
    poll();

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [currentRequestId, router]);

  return (
    <Layout background="url('/bg-redato.png') no-repeat center center fixed">
      {!showModal && (
        <>
          <div className={styles.formContainer}>
            <div className={styles.themeSection}>
              <label className={styles.labels}>Tema:</label>
              <div className={styles.customDropdownContainer} ref={dropdownRef}>
                <div 
                  className={`${styles.customDropdownHeader} 
                    ${isDropdownOpen ? styles.active : ''} 
                    ${selectedThemeId ? styles.selected : ''} 
                    ${(loading || loadingThemes) ? styles.disabled : ''}`}
                  onClick={() => !loading && !loadingThemes && setIsDropdownOpen(!isDropdownOpen)}
                >
                  <span>
                    {loadingThemes 
                      ? "Carregando temas..." 
                      : selectedThemeId === "tema-livre"
                        ? "Tema Livre"
                        : selectedThemeId
                          ? themes.find(t => t.id === selectedThemeId)?.name || "Selecione um tema"
                          : themes.length > 0 
                            ? "Selecione um tema" 
                            : "Nenhum tema disponível"
                    }
                  </span>
                  <ChevronDown 
                    size={16} 
                    className={`${styles.dropdownIcon} ${isDropdownOpen ? styles.open : ''}`} 
                  />
                </div>
                
                {isDropdownOpen && (
                  <div className={styles.customDropdownList}>
                    <div 
                      className={`${styles.customDropdownItem} ${selectedThemeId === "tema-livre" ? styles.selected : ''}`}
                      onClick={() => handleThemeSelect("tema-livre")}
                    >
                      Tema Livre
                    </div>
                    {themes.length > 0 ? (
                      themes.map((theme) => (
                        <div 
                          key={theme.id} 
                          className={`${styles.customDropdownItem} ${selectedThemeId === theme.id ? styles.selected : ''}`}
                          onClick={() => handleThemeSelect(theme.id, theme.name)}
                        >
                          {theme.name}
                        </div>
                      ))
                    ) : (
                      <div className={styles.customDropdownNoItems}>
                        Nenhum tema disponível
                      </div>
                    )}
                  </div>
                )}
                
                {loadingThemes && (
                  <div className={styles.loadingIndicator} title="Carregando temas...">
                    ⟳
                  </div>
                )}
                
                {selectedThemeId && (
                  <button 
                    type="button"
                    className={styles.infoButton}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleShowThemeDescription(selectedThemeId);
                    }}
                    aria-label="Informações sobre o tema"
                  >
                    <Info size={18} />
                  </button>
                )}
              </div>
              
              {showThemeDescription && (
                <div 
                  className={styles.themeDescriptionPopup}
                  onClick={(e) => {
                    // Fecha a modal se o clique for no fundo escuro
                    if (e.target === e.currentTarget) {
                      setShowThemeDescription(false);
                    }
                  }}
                >
                  <div className={styles.themeDescriptionContent}>
                    <button 
                      className={styles.closeDescriptionButton}
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowThemeDescription(false);
                      }}
                      aria-label="Fechar descrição"
                    >
                      ×
                    </button>
                    <h3>Descrição do Tema</h3>
                    <p>{themeDescriptionToShow}</p>
                  </div>
                </div>
              )}
              
              {selectedThemeId === "tema-livre" && (
                <>
                  <input
                    type="text"
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                    className={styles.inputField}
                    disabled={loading}
                    placeholder="Digite o tema da sua redação"
                  />
                </>
              )}
              
              <label className={styles.labels}>Escreva sua redação:</label>
              {ocrAccuracy !== null && ocrAccuracy < OCR_ACCURACY_WARNING_THRESHOLD && (
                <div
                  style={{
                    background: "#FEF3C7",
                    border: "1px solid #FCD34D",
                    borderRadius: "6px",
                    padding: "10px 14px",
                    marginBottom: "10px",
                    color: "#92400E",
                    fontSize: "13px",
                  }}
                >
                  <strong>Atenção:</strong> a leitura da sua imagem teve confiança
                  de {Math.round(ocrAccuracy * 100)}%. Revise o texto abaixo com
                  cuidado e corrija os trechos destacados antes de enviar.
                </div>
              )}
              {content.includes('<uncertain') ? (
                <div className={`${styles.textareaField} ${styles.readOnlyContent}`}>
                  <HighlightedText 
                    text={content} 
                    onChange={handleContentChange} 
                  />
                </div>
              ) : (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className={styles.textareaField}
                  disabled={loading}
                  placeholder="Escreva sua redação aqui..."
                />
              )}
            </div>
          </div>
          <div className={styles.buttonContainer}>
            <button onClick={handleTextSubmit} className={styles.submitButton} disabled={loading}>
              {loading ? "Processando..." : "Enviar Redação"}
            </button>
          </div>
        </>
      )}

      {showModal && (
        <div className={styles.modalSend}>
          <img
            src="/icone-preto.png"
            alt="Loading"
            className={`${styles.loadingLogo} ${
              modalMessage.includes("corrigida") || modalMessage.includes("Erro:") ? styles.paused : ""
            }`}
          />
          <div className={styles.textSend}>
            {(() => {
              const hasPreview =
                displayedPreview &&
                !modalMessage.includes("corrigida") &&
                !modalMessage.includes("Erro:");
              if (hasPreview) {
                return (
                  <p
                    style={{
                      margin: 0,
                      fontSize: "15px",
                      fontWeight: 400,
                      lineHeight: 1.5,
                      color: "#0F172A",
                      maxWidth: "440px",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {displayedPreview}
                    <span
                      style={{
                        display: "inline-block",
                        width: "6px",
                        height: "15px",
                        background: "#0F172A",
                        marginLeft: "3px",
                        verticalAlign: "text-bottom",
                        animation: "redatoCursorBlink 0.9s steps(2) infinite",
                      }}
                    />
                    <style>{`@keyframes redatoCursorBlink { 0%,49%{opacity:1} 50%,100%{opacity:0} }`}</style>
                  </p>
                );
              }
              return <h2>{modalMessage}</h2>;
            })()}
            {modalMessage.includes("Erro:") && (
              <p>
                Ocorreu um erro ao enviar sua redação.
                <br />
                Não se preocupe, sua redação foi salva.
              </p>
            )}
            {showButtons && (
              <div className={styles.buttonGroup}>
                {modalMessage.includes("Erro:") ? (
                  <button
                    className={styles.dashboardButton}
                    onClick={() => {
                      setShowModal(false);
                    }}
                  >
                    Voltar para a redação
                  </button>
                ) : (
                  <>
                    <button
                      className={styles.dashboardButton}
                      onClick={() => {
                        localStorage.removeItem("ocrPreFillContent");
                        localStorage.removeItem("ocrPreFillTheme");
                        localStorage.removeItem("ocrAccuracy");
                        localStorage.removeItem("ocrRequestId");
                        router.push("/dashboard");
                      }}
                    >
                      Dashboard
                    </button>
                    <button
                      className={styles.studyPlanButton}
                      onClick={() => {
                        localStorage.removeItem("ocrPreFillContent");
                        localStorage.removeItem("ocrPreFillTheme");
                        localStorage.removeItem("ocrAccuracy");
                        localStorage.removeItem("ocrRequestId");
                        router.push("/correcao");
                      }}
                    >
                      Ver Correção
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}