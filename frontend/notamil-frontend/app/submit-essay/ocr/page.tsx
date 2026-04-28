"use client";

import { useState, useEffect, useRef } from "react";
import Layout from "../../dashboard/components/Layout";
import styles from "../submit-essay.module.css";
import { useRouter } from "next/navigation";
import { Camera } from "lucide-react";

type JobStatus = "pending" | "processing" | "completed" | "failed" | "not_found";

interface OcrResultData {
  request_id: string;
  status?: JobStatus;
  data?: any;
  detail_url?: string;
  error?: string | null;
}

interface OcrSubmitResponse {
  request_id?: string;
  status?: JobStatus;
  error?: string;
  detail?: string;
}

const POLLING_INTERVAL_MS = 3000;
const MAX_POLLING_MS = 10 * 60 * 1000; // 10 min hard cap
const MAX_POLLING_ATTEMPTS = Math.ceil(MAX_POLLING_MS / POLLING_INTERVAL_MS);

export default function SubmitEssayOCR() {
  const router = useRouter();

  // Estados para o fluxo OCR
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const finalStatusReceived = useRef(false);

  // Referencias para inputs ocultos
  const inputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Estado para mensagem de log (opcional, para depuração)
  const [modalMessage, setModalMessage] = useState("🚀 Imagem enviada! Aguardando análise...");

  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;

  // Verifica se o dispositivo é móvel
  useEffect(() => {
    const checkMobile = () => {
      const userAgent = 
        typeof window !== "undefined" && window.navigator.userAgent.toLowerCase();
      const isMobileDevice = 
        /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent || '');
      setIsMobile(isMobileDevice);
    };
    
    checkMobile();
  }, []);

  // Função para tratar o resultado final
  const handleFinalResult = (resultData: any) => {
    const requestId = currentRequestId;

    if (resultData.data && resultData.data.theme && resultData.data.content) {
      console.log("✅ Dados completos recebidos:", resultData.data);
      localStorage.setItem("ocrPreFillTheme", resultData.data.theme);
      localStorage.setItem("ocrPreFillContent", resultData.data.content);
      if (requestId) {
        localStorage.setItem("ocrRequestId", requestId);
      } else {
        localStorage.removeItem("ocrRequestId");
      }
      if (typeof resultData.data.accuracy === "number") {
        localStorage.setItem("ocrAccuracy", String(resultData.data.accuracy));
      } else {
        localStorage.removeItem("ocrAccuracy");
      }
      localStorage.setItem("correctionData", JSON.stringify(resultData.data));
      router.push("/submit-essay/text");
    } else if (resultData.detail_url) {
      fetch(resultData.detail_url)
        .then((res) => res.json())
        .then((data) => {
          if (data && data.data && data.data.theme && data.data.content) {
            console.log("✅ Dados completos recebidos via detail_url:", data.data);
            localStorage.setItem("ocrPreFillTheme", data.data.theme);
            localStorage.setItem("ocrPreFillContent", data.data.content);
            if (requestId) {
              localStorage.setItem("ocrRequestId", requestId);
            } else {
              localStorage.removeItem("ocrRequestId");
            }
            localStorage.setItem("correctionData", JSON.stringify(data.data));
            router.push("/submit-essay/text");
          } else {
            console.error("❌ Erro: Dados da análise não encontrados via detail_url.");
            setUploadError("Não foi possível extrair o texto da imagem.");
          }
        })
        .catch((err) => {
          console.error("❌ Erro ao buscar análise via detail_url:", err);
          setUploadError("Erro ao processar a resposta do servidor.");
        });
    } else {
      console.warn("⚠️ Resultado incompleto recebido.");
      setModalMessage("⏳ Ainda aguardando análise...");
      // Não redireciona, permitindo que o polling continue
    }
  };

  // Otimiza e converte a imagem para um tamanho mais adequado
  const optimizeImage = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (!event.target?.result) {
          reject("Falha ao ler a imagem");
          return;
        }
        
        const img = new Image();
        img.onload = () => {
          const canvas = canvasRef.current || document.createElement('canvas');
          
          // 1800px preserva detalhe de pixel pra acentos, til, distinção rn/m
          // (manuscrito tem traços finos que 1200px borrava). Trade-off:
          // arquivo ~2x maior, upload +1-2s em 4G.
          const MAX_WIDTH = 1800;
          
          let width = img.width;
          let height = img.height;
          
          // Redimensione se for maior que a largura máxima
          if (width > MAX_WIDTH) {
            height = Math.floor(height * (MAX_WIDTH / width));
            width = MAX_WIDTH;
          }
          
          canvas.width = width;
          canvas.height = height;
          
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            reject("Não foi possível obter o contexto do canvas");
            return;
          }
          
          // Desenhe a imagem no canvas com as novas dimensões
          ctx.drawImage(img, 0, 0, width, height);
          
          // JPEG 0.92 evita artefatos de compressão em traços finos.
          try {
            const base64Data = canvas.toDataURL('image/jpeg', 0.92).split(',')[1];
            resolve(base64Data);
          } catch (err) {
            console.error("Erro ao converter canvas para base64:", err);
            reject("Erro ao otimizar a imagem");
          }
        };
        
        img.onerror = () => {
          reject("Erro ao carregar a imagem");
        };
        
        img.src = event.target.result as string;
      };
      
      reader.onerror = (error) => {
        reject(error);
      };
      
      reader.readAsDataURL(file);
    });
  };

  // Envia a imagem para OCR
  const handleImageSubmit = async () => {
    if (!selectedFile) {
      setUploadError("Nenhuma imagem selecionada!");
      return;
    }
    
    setUploadError(null);
    finalStatusReceived.current = false;
    setCurrentRequestId(null);
    setLoading(true);
    setModalMessage("🚀 Imagem enviada! Aguardando análise...");
    
    if (!userId) {
      setUploadError("Usuário não autenticado!");
      setLoading(false);
      return;
    }
    
    try {
      // Usa a função de otimização em vez da conversão direta
      const base64File = await optimizeImage(selectedFile);
      
      console.log("Enviando imagem otimizada para OCR...");
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/ocr`,
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ user_id: userId, base64_file: base64File }),
        }
      );
      
      const data: OcrSubmitResponse = await response.json();

      if (!response.ok || data.status === "failed") {
        const message =
          data.error || data.detail || "Erro ao processar a imagem.";
        throw new Error(message);
      }

      if (!data.request_id) {
        throw new Error("O servidor não retornou um identificador.");
      }

      setCurrentRequestId(data.request_id);
      setModalMessage("Imagem enviada. Aguardando análise...");
    } catch (error: any) {
      console.error("Erro ao enviar imagem:", error);
      setUploadError(`Erro: ${error.message}`);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!currentRequestId || finalStatusReceived.current) return;
    let attempts = 0;
    let cancelled = false;

    const poll = async () => {
      if (cancelled || finalStatusReceived.current) return;
      attempts += 1;
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/essays/result/ocr/${currentRequestId}`
        );
        const data: OcrResultData = await response.json();

        if (response.status === 422 || data.status === "failed") {
          finalStatusReceived.current = true;
          setUploadError(
            `Erro: ${data.error || "Não foi possível extrair o texto da imagem."}`
          );
          setLoading(false);
          return;
        }

        if (
          response.ok &&
          data.status === "completed" &&
          data.data &&
          data.data.theme &&
          data.data.content
        ) {
          finalStatusReceived.current = true;
          handleFinalResult(data);
          return;
        }

        if (attempts >= MAX_POLLING_ATTEMPTS) {
          finalStatusReceived.current = true;
          setUploadError(
            "Erro: A análise está demorando mais do que o esperado. Tente novamente em alguns minutos."
          );
          setLoading(false);
          return;
        }

        setModalMessage(
          `Ainda aguardando análise... ${new Date().toLocaleTimeString()}`
        );
      } catch (err) {
        console.error("Erro durante polling:", err);
        if (attempts >= MAX_POLLING_ATTEMPTS) {
          finalStatusReceived.current = true;
          setUploadError(
            "Erro: Não foi possível obter o resultado. Verifique sua conexão e tente novamente."
          );
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

  // Funções para a Drop Zone
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setUploadError(null);
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      setSelectedFile(files[0]);
    }
  };

  const handleFileSelectClick = () => {
    inputRef.current?.click();
  };

  const handleCameraClick = () => {
    cameraInputRef.current?.click();
  };

  const handleCancelUpload = () => {
    setSelectedFile(null);
    setUploadError(null);
  };

  return (
    <Layout background="url('/bg-redato.png') no-repeat center center fixed">
      <div className={styles.uploadContainer} onDragOver={handleDragOver} onDrop={handleDrop}>
        {!selectedFile ? (
          <>
            <div className={styles.buttons}>
              <button className={styles.button} onClick={handleFileSelectClick}>
                📂 Selecionar Imagem
              </button>
              
              {isMobile && (
                <button className={styles.button} onClick={handleCameraClick}>
                  <Camera size={18} /> Usar Câmera
                </button>
              )}
            </div>
            <p className={styles.hint}>Ou arraste e solte a imagem aqui</p>
            
            {uploadError && (
              <p className={styles.errorMessage}>{uploadError}</p>
            )}
          </>
        ) : (
          <>
            <div className={styles.uploadPreview}>
              <img
                src={URL.createObjectURL(selectedFile)}
                alt="Miniatura da imagem"
                className={styles.thumbnail}
              />
              <button className={styles.cancelButton} onClick={handleCancelUpload}>
                X
              </button>
            </div>
            
            {uploadError && (
              <p className={styles.errorMessage}>{uploadError}</p>
            )}
            
            <button
               onClick={handleImageSubmit} 
               className={styles.submitButton} 
               disabled={loading}>
              {loading ? "Processando..." : "Enviar Redação"}
            </button>
          </>
        )}
      </div>
      
      {/* Canvas oculto para otimização de imagem */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />
      
      {/* Input de arquivo oculto para seleção da galeria */}
      <input
        type="file"
        accept="image/*"
        ref={inputRef}
        style={{ display: "none" }}
        onChange={(e) => {
          setUploadError(null);
          const file = e.target.files?.[0];
          if (file) {
            setSelectedFile(file);
          }
        }}
      />
      
      {/* Input de arquivo oculto para câmera */}
      <input
        type="file"
        accept="image/*"
        capture="environment"
        ref={cameraInputRef}
        style={{ display: "none" }}
        onChange={(e) => {
          setUploadError(null);
          const file = e.target.files?.[0];
          if (file) {
            setSelectedFile(file);
          }
        }}
      />
    </Layout>
  );
}