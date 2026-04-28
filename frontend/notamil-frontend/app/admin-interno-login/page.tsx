'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Box, Button } from '@mui/material'
import Link from 'next/link'
import styles from './admin-interno.module.css'

// Firebase
import { signInWithEmailAndPassword } from '@/services/authSdk'
import { auth } from '@/services/firebaseClient'
import { saveUserData } from '@/app/utils/storage'

export const dynamic = 'force-dynamic';

export default function AdminLoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      console.log("Iniciando processo de login de admin interno...")
      
      // 1) Login Firebase
      const userCredential = await signInWithEmailAndPassword(auth, email, password)

      // 2) Pega o ID do usuário autenticado no Firebase
      const userId = userCredential.user.uid
      console.log("Admin autenticado no Firebase! ID:", userId)

      // 3) Armazena o user_id no localStorage
      localStorage.setItem('user_id', userId)
      console.log("User ID salvo no localStorage")

      // 4) Pega o token do Firebase
      const firebaseToken = await userCredential.user.getIdToken()
      console.log("Token obtido do Firebase")

      // 5) Faz o POST para a API
      console.log("Fazendo requisição para API:", `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`)
      
      const payload = {
        user_id: userId
      };
      
      console.log("Payload enviado:", payload);
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${firebaseToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      console.log("Resposta da API:", response.status)

      if (!response.ok) {
        throw new Error(`Falha na resposta da API: ${response.status}`)
      }

      try {
        // Processar a resposta da API
        const responseData = await response.json()
        console.log("Dados da resposta:", responseData)
        
        // Guardar os dados do usuário no localStorage
        saveUserData({
          user_id: responseData.user_id,
          role: responseData.role,
          name: responseData.username,
          school_id: responseData.school_id
        });
        
        // Verificar se é admin
        if (responseData.role === 'school_admin') {
          // Redirecionar para o dashboard de admin
          router.push('/admin-interno');
        } else {
          setError('Acesso negado. Esta área é restrita a administradores internos.');
          setLoading(false);
        }
        
      } catch (jsonError) {
        console.error("Erro ao processar JSON da resposta:", jsonError)
        setError('Erro ao processar resposta do servidor.');
        setLoading(false);
      }

    } catch (error) {
      console.error("Erro durante login:", error)
      setError('Email ou senha incorretos')
      setLoading(false);
    }
  }

  return (
    <Box className={styles.loginContainer}>
      {/* Seção do topo (Admin Interno) */}
      <Box className={styles.topSection}>
        Admin Interno
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
            <Link href="/login" className={styles.registerLink}>
              Entrar como aluno
            </Link>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
