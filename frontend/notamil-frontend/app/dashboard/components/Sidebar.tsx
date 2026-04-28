"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutGrid,
  FileText,
  BookOpen,
  PenTool,
  User2,
  Bell,
  Settings,
  LogOut,
  Menu,
  X,
  User
} from "lucide-react";
import styles from "./Sidebar.module.css";

// Define a interface para as props
interface SidebarProps {
  role: "aluno" | "professor";
}

const menuItems = [
  { icon: LayoutGrid, text: "Dashboard", href: "/dashboard" },
  { icon: FileText, text: "Relatórios", href: "/correcao" },
  { icon: BookOpen, text: "Plano de Estudo", href: "/study-plan" },
];

const bottomMenuItems = [
  { icon: User2, text: "Profile", href: "/profile" },
];

export default function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();
  const [userName, setUserName] = useState("");

  // Estados para controle da responsividade e visibilidade
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  // Efeito para buscar o nome do localStorage no lado do cliente
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedName = localStorage.getItem("user_name") || "Usuário";
      setUserName(storedName);
    }
  }, []);

  // Função para alternar o sidebar - mantendo a simplicidade
  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  // Função para fechar o sidebar em dispositivos móveis
  const closeSidebar = () => {
    if (isMobile) {
      setIsSidebarOpen(false);
    }
  };

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1100) {
        setIsMobile(true);
        setIsSidebarOpen(false);
      } else {
        setIsMobile(false);
        setIsSidebarOpen(true);
      }
    };

    // Executa no carregamento inicial
    handleResize();

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Impede o scroll do body quando a sidebar está aberta em mobile
  useEffect(() => {
    if (isMobile && isSidebarOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobile, isSidebarOpen]);

  // Filtragem condicional dos itens do menu
  const filteredMenuItems = menuItems.filter((item) => {
    if (role === "professor") {
      // Para professor, não mostrar nenhum item além do Dashboard
      return false;
    } else {
      // Para aluno, não mostrar Dashboard (já está no item principal)
      return item.text !== "Dashboard";
    }
  });

  // Ajusta o href do Dashboard principal baseado no role
  const dashboardHref = role === "professor" ? "/professor" : "/dashboard";

  return (
    <>
      {/* Overlay para fechar o sidebar em dispositivos móveis */}
      {isMobile && isSidebarOpen && (
        <div 
          className={styles.overlay}
          onClick={closeSidebar}
        />
      )}

      {/* Botão hamburger aparece apenas em dispositivos móveis */}
      {isMobile && (
        <button
          className={`${styles.hamburgerButton} ${isSidebarOpen ? styles.hamburgerButtonActive : ''}`}
          onClick={toggleSidebar}
        >
          {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      )}

      {/* Sidebar com classe condicional para mobile */}
      <aside
        className={`${styles.sidebar} ${
          isMobile && !isSidebarOpen ? styles.closed : ""
        }`}
      >
        <div className={styles.sidebarContent}>
          {/* Logo */}
          <div className={styles.logoContainer}>
            <Image 
              src="/logo-header.png" 
              alt="Logo" 
              width={40} 
              height={40} 
              priority
            />
          </div>

          {/* Main Navigation */}
          <nav className={styles.mainNav}>
            {/* Exibe o botão de Envio de Redação somente para alunos */}
            {role === "aluno" && (
              <Link
                href="/select"
                className={`${styles.navItem} ${
                  pathname.startsWith("/select") ? styles.active : ""
                } ${styles.redactionButton}`}
                onClick={closeSidebar}
              >
                <PenTool size={20} className={styles.navIcon} />
                <span>Envio de Redação</span>
              </Link>
            )}

            <hr className={styles.divider} />

            {/* Item Dashboard com href dinâmico */}
            <Link
              key="Dashboard"
              href={dashboardHref}
              className={`${styles.navItem} ${
                // Verifica se o pathname atual corresponde ao href do dashboard
                pathname === dashboardHref ? styles.active : ""
              }`}
              onClick={closeSidebar}
            >
              <LayoutGrid size={20} className={styles.navIcon} />
              <span>Dashboard</span>
            </Link>

            {/* Renderiza os itens restantes filtrados (apenas para aluno) */}
            {filteredMenuItems.map((item) => (
              <Link
                key={item.text}
                href={item.href}
                className={`${styles.navItem} ${
                  pathname.startsWith(item.href) ? styles.active : ""
                }`}
                onClick={closeSidebar}
              >
                <item.icon size={20} className={styles.navIcon} />
                <span>{item.text}</span>
              </Link>
            ))}
          </nav>

          {/* User Section */}
          <div className={styles.userSection}>
            <div className={styles.userInfo}>
              <div className={styles.userDetails}>
                <span className={styles.userRole}>
                  {role === "aluno" ? "Aluno" : "Professor"}
                </span>
                <div className={styles.userName}>
                  <span className={styles.userNameText}>{userName}</span>
                </div>
              </div>
            </div>

            {/* Bottom Navigation */}
            <nav className={styles.bottomNav}>
              {bottomMenuItems.map((item) => (
                <Link
                  key={item.text}
                  href={item.href}
                  className={`${styles.navItem} ${
                    pathname.startsWith(item.href) ? styles.active : ""
                  }`}
                  onClick={closeSidebar}
                >
                  <item.icon size={20} className={styles.navIcon} />
                  <span>{item.text}</span>
                </Link>
              ))}
            </nav>

            {/* Logout */}
            <div className={styles.navItem}>
              <Link
                className={styles.logout}
                href="/login"
                onClick={() => {
                  localStorage.removeItem("ocrPreFillContent");
                  localStorage.removeItem("ocrPreFillTheme");
                  localStorage.removeItem("correctionData");
                  localStorage.removeItem("user_id");
                  localStorage.removeItem("role");
                }}
              >
                <LogOut size={20} />
                <span>Logout</span>
              </Link>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}