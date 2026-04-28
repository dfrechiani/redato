// app/submit-essay/select/page.tsx (ou conforme sua estrutura de rotas)
"use client";
import { useRouter } from "next/navigation";
import Layout from "../dashboard/components/Layout";
import styles from "./select.module.css"; // Crie um CSS simples para essa tela

export default function SelectSubmissionPage() {
  const router = useRouter();
  return (
    <Layout background="url('/bg-redato.png') no-repeat center center fixed">
      <div className={styles.selectContainer}>
        <h2>Como prefere<br /> enviar sua redação?</h2>
        <div className={styles.buttons}>
          <button 
            onClick={() => {
              localStorage.removeItem("ocrPreFillContent");
              localStorage.removeItem("ocrPreFillTheme");
              localStorage.removeItem("correctionData");
              router.push("/submit-essay/text")}
            }
          >
            ✍️ Digitar
          </button>
          <button
            onClick={() => {
              localStorage.removeItem("ocrPreFillContent");
              localStorage.removeItem("ocrPreFillTheme");
              localStorage.removeItem("correctionData");
              router.push("/submit-essay/ocr")}
            }
          >
            📂 Fazer Upload
          </button>
        </div>
      </div>
    </Layout>
  );
}
