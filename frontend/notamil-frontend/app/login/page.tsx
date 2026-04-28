'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Box, Button } from '@mui/material'
import Link from 'next/link'
import styles from './Login.module.css'

// Firebase (offline-aware wrapper)
import { signInWithEmailAndPassword } from '@/services/authSdk'
import { auth } from '@/services/firebaseClient'
import { saveUserData } from '@/app/utils/storage'

export const dynamic = 'force-dynamic';

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showRedirectPopup, setShowRedirectPopup] = useState(false)
  
  const router = useRouter()

  // No seu arquivo login.tsx, modifique a função handleSubmit:

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      console.log("Iniciando processo de login...")
      
      // 1) Login Firebase
      const userCredential = await signInWithEmailAndPassword(auth, email, password)

      // 2) Pega o ID do usuário autenticado no Firebase
      const userId = userCredential.user.uid
      console.log("Usuário autenticado no Firebase! ID:", userId)

      // 3) Armazena o user_id no localStorage
      localStorage.setItem('user_id', userId)
      console.log("User ID salvo no localStorage")

      // 4) Pega o token do Firebase
      const firebaseToken = await userCredential.user.getIdToken()
      console.log("Token obtido do Firebase")

      // 5) Faz o POST para a API
      console.log("Fazendo requisição para API:", `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`)
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${firebaseToken}`,
          'Content-Type': 'application/json',
        },
      })

      console.log("Resposta da API:", response.status)

      if (!response.ok) {
        throw new Error(`Falha na resposta da API: ${response.status}`)
      }

      // 6) Recebe os dados do usuário incluindo o role
      const userData = await response.json()
      console.log("Dados recebidos da API:", userData)

      if (!userData.role) {
        throw new Error("Seu usuário não tem um perfil atribuído. Contate o administrador.")
      }

      const userRole = userData.role as string

      // 7) Armazena os dados do usuário no localStorage
      saveUserData({
        user_id: userId,
        role: userRole,
        name: userData.name || email.split('@')[0],
        class_id: userData.class_id
      });

      console.log("Dados salvos no localStorage:", {
        user_id: localStorage.getItem('user_id'),
        user_role: localStorage.getItem('user_role'),
        user_name: localStorage.getItem('user_name'),
        class_id: localStorage.getItem('class_id')
      })

      // 8) Redireciona com base no role
      if (userRole === 'professor') {
        console.log("Usuário é professor, mostrando popup de redirecionamento")
        setShowRedirectPopup(true)
        setLoading(false)
        return
      } else {
        console.log("Redirecionando para /dashboard")
        router.push('/dashboard')
      }

    } catch (error) {
      console.error("Erro durante login:", error)
      setError('Email ou senha incorretos')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box className={styles.loginContainer}>
      {/* Seção do topo (Aluno) */}
      <Box className={styles.topSection}>
        Aluno
      </Box>

      {/* Logo */}
      <Box className={styles.logoSection}>
        <img
          src="/logo-login.png"
          alt="Logo"
          className={styles.logo}
        />
      </Box>

      {/* Formulário de Login */}
      <Box className={styles.formContainer}>
        <Box 
          component="form" 
          onSubmit={handleSubmit}
          className={styles.formWrapper}
        >
          <Box className={styles.formGroup}>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={styles.customTextField}
            />
          </Box>

          <Box className={styles.formGroup}>
            <input
              type="password"
              placeholder="Senha"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.customTextField}
            />
          </Box>

          {error && <div className={styles.errorMessage}>{error}</div>}

          <Button
            type="submit"
            className={styles.submitButton}
            variant="contained"
            disabled={loading}
          >
            {loading ? 'ENTRANDO...' : 'ENTRAR'}
          </Button>

          <Box className={styles.registerLinkContainer}>
            <Link href="/register" className={styles.registerLink}>
              Não tenho conta ainda
            </Link>
            <div className={styles.professorLinkContainer}>
              <Link href="/professor-login" className={styles.professorLink}>
                Entrar como professor
              </Link>
            </div>
          </Box>
        </Box>
      </Box>

      {/* Pop-up de redirecionamento */}
      {showRedirectPopup && (
        <div className={styles.popupOverlay}>
          <div className={styles.popup}>
            <div className={styles.popupContent}>
              <h3>Detectamos que você é um professor!</h3>
              <p>Esta página é destinada a alunos. Deseja ir para a área de login de professor?</p>
              <div className={styles.popupButtons}>
                <button 
                  className={styles.popupButtonCancel}
                  onClick={() => setShowRedirectPopup(false)}
                >
                  Cancelar
                </button>
                <button 
                  className={styles.popupButtonConfirm}
                  onClick={() => router.push('/professor-login')}
                >
                  Ir para login de professor
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Box>
  )
}