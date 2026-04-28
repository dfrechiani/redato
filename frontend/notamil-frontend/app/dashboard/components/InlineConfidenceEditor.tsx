"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import styles from "../../submit-essay/submit-essay.module.css";

interface Segment {
  type: "text" | "confidence";
  content: string;
  originalTag?: string; // Tag original, se quiser manipular
  edited: boolean;
}

interface InlineConfidenceEditorProps {
  initialText: string;
  onChange: (plainText: string) => void;
}

// Função para identificar e separar os trechos <uncertain>...</uncertain>
const parseText = (text: string): Segment[] => {
  if (!text) return [];
  
  const segments: Segment[] = [];
  let currentIndex = 0;
  
  // Regex que pega <uncertain ...>...</uncertain>, incluindo quaisquer atributos (ex: confidence='HIGH')
  const regex = /<uncertain\b[^>]*>(.*?)<\/uncertain>/g;
  let match;
  
  while ((match = regex.exec(text)) !== null) {
    // Se houver texto normal antes da tag <uncertain>, adiciona como "text"
    if (match.index > currentIndex) {
      segments.push({
        type: "text",
        content: text.slice(currentIndex, match.index),
        edited: true, // texto normal não tem edição
      });
    }
    
    // Trecho capturado como "confidence"
    segments.push({
      type: "confidence",
      content: match[1],       // só o conteúdo dentro de <uncertain>...</uncertain>
      originalTag: match[0],   // caso queira armazenar a tag inteira
      edited: false,           // inicia como não editado
    });
    
    currentIndex = regex.lastIndex;
  }
  
  // Se ainda sobrou texto após a última tag <uncertain>
  if (currentIndex < text.length) {
    segments.push({
      type: "text",
      content: text.slice(currentIndex),
      edited: true,
    });
  }
  
  return segments;
};

interface ConfidenceSegmentProps {
  segment: Segment;
  editing: boolean;
  onFinishEditing: (newText: string) => void;
  onStartEditing: () => void;
}

const ConfidenceSegment: React.FC<ConfidenceSegmentProps> = ({
  segment,
  editing,
  onFinishEditing,
  onStartEditing,
}) => {
  const spanRef = useRef<HTMLSpanElement>(null);

  // Foca o cursor no final do texto quando inicia a edição
  useEffect(() => {
    if (editing && spanRef.current) {
      spanRef.current.focus();
      
      const range = document.createRange();
      range.selectNodeContents(spanRef.current);
      range.collapse(false);
      
      const sel = window.getSelection();
      if (sel) {
        sel.removeAllRanges();
        sel.addRange(range);
      }
    }
  }, [editing]);

  if (editing) {
    // Modo edição (contentEditable)
    return (
      <span
        ref={spanRef}
        contentEditable
        suppressContentEditableWarning
        className={`${styles.corrected} ${styles.editing}`}
        style={{ display: "inline-block", minWidth: "2ch" }}
        onBlur={(e) => {
          onFinishEditing(e.currentTarget.textContent || "");
        }}
      >
        {segment.content}
      </span>
    );
  }

  // Modo leitura (não editando)
  return (
    <span
      className={segment.edited ? styles.corrected : styles.uncertain}
      style={{ cursor: "pointer", display: "inline-block", minWidth: "2ch" }}
      title="Clique para corrigir. Após editar, o texto ficará verde."
      onClick={onStartEditing}
    >
      {segment.content}
    </span>
  );
};

const InlineConfidenceEditor: React.FC<InlineConfidenceEditorProps> = ({
  initialText,
  onChange,
}) => {
  // Monta os "segments" com base no texto inicial
  const initialSegments = useMemo(() => parseText(initialText), [initialText]);
  const [segments, setSegments] = useState<Segment[]>(initialSegments);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  // Sempre que segments mudar, atualizamos o texto puro (sem tags <uncertain>)
  useEffect(() => {
    const plainText = segments.map((seg) => seg.content).join("");
    onChange(plainText);
  }, [segments, onChange]);

  // Função que finaliza a edição de um trecho
  const finishEditing = (index: number, newText: string) => {
    setSegments((prev) =>
      prev.map((seg, i) =>
        i === index ? { ...seg, content: newText, edited: true } : seg
      )
    );
    setEditingIndex(null);
  };

  // Função que inicia a edição (permite re-editar mesmo se editado)
  const startEditing = (index: number) => {
    setEditingIndex(index);
  };

  // Renderiza cada segmento
  const renderSegment = (segment: Segment, index: number) => {
    if (segment.type === "confidence") {
      return (
        <ConfidenceSegment
          key={index}
          segment={segment}
          editing={editingIndex === index}
          onFinishEditing={(newText) => finishEditing(index, newText)}
          onStartEditing={() => startEditing(index)}
        />
      );
    } else {
      // Segmentos de texto normal (fora de <uncertain>...</uncertain>)
      return <span key={index}>{segment.content}</span>;
    }
  };

  return (
    <div
      contentEditable={false} // Impede edição direta no container
      className={styles.editor}
    >
      {segments.length > 0
        ? segments.map((seg, i) => renderSegment(seg, i))
        : initialText}
    </div>
  );
};

export default InlineConfidenceEditor;
