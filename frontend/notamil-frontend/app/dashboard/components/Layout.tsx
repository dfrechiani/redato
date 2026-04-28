"use client";
import { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import styles from "./Layout.module.css";
import { motion } from "framer-motion";

interface LayoutProps {
  children: React.ReactNode;
  background?: string;
  role?: "aluno" | "professor";
  headerContent?: React.ReactNode; // Conteúdo opcional para o header
  showHeaderBorder?: boolean; // Opção para mostrar borda no header
}

export default function Layout({ 
  children, 
  background, 
  role = "aluno",
  headerContent,
  showHeaderBorder = false
}: LayoutProps) {
  const [scrolled, setScrolled] = useState(false);

  // Detecta quando a página é rolada
  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 10) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className={styles.layout} style={{ background }}>
      {/* Header fixo que permanece no topo durante a rolagem */}
      <header 
        className={`${styles.fixedHeader} ${scrolled || showHeaderBorder ? styles.fixedHeaderWithBorder : ''}`}
      >
        {headerContent}
      </header>

      <Sidebar role={role} />
      
      <motion.div
        className={styles.content}
        initial={{ opacity: 0, x: 0 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 0 }}
        transition={{ duration: 0.3 }}
      >
        {children}
      </motion.div>
    </div>
  );
}