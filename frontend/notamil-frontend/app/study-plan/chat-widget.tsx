"use client"

import type React from "react"
import { useState, useRef, useEffect } from "react"
import styles from "./study-plan.module.css"
import { auth } from "@/services/firebaseClient"
import { authFetch } from "@/services/authFetch"

interface ChatWidgetProps {
  competency: string;
  errorSnippet: string;
  errorType: string;
  userId: string;
  essay_id?: string;
  onClose: () => void;
}

export default function ChatWidget({ competency, errorSnippet, errorType, userId, essay_id, onClose }: ChatWidgetProps) {
  // Mensagem inicial personalizada do tutor:
  const initialTutorMessage = `Vamos trabalhar no seguinte trecho da sua redação:
"${errorSnippet}"
Este trecho apresenta um problema de ${errorType}.
Você entende por que isso é considerado um erro? Se tiver dúvidas, fique à vontade para perguntar.`

  const [chatInput, setChatInput] = useState("")
  const [messages, setMessages] = useState<
    { sender: "user" | "tutor"; text: string; timestamp?: string; isTyping?: boolean }[]
  >([
    {
      sender: "tutor",
      text: initialTutorMessage,
      timestamp: "",
    },
  ])
  const [loading, setLoading] = useState(false)
  const [showOptions, setShowOptions] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Load stored conversation history when the widget mounts so the student
  // can see past exchanges about this essay.
  useEffect(() => {
    if (!essay_id || !userId) return

    let cancelled = false
    ;(async () => {
      try {
        const response = await authFetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/intelligence/tutor/history?essay_id=${encodeURIComponent(
            essay_id
          )}&user_id=${encodeURIComponent(userId)}`
        )
        if (!response.ok) return
        const data = await response.json()
        if (cancelled) return
        const historical = (data?.messages || []).filter(
          (m: any) => typeof m.content === "string" && m.content.trim() !== ""
        )
        if (historical.length === 0) return

        setMessages([
          {
            sender: "tutor",
            text: initialTutorMessage,
            timestamp: "",
          },
          ...historical.map((m: any) => ({
            sender: m.role === "user" ? ("user" as const) : ("tutor" as const),
            text: m.content,
            timestamp: "",
          })),
        ])
        setShowOptions(false)
      } catch (err) {
        console.error("Erro ao carregar histórico do tutor:", err)
      }
    })()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [essay_id, userId])

  const chat_id = "chat_" + Date.now()

  const animateText = async (text: string, messageIndex: number) => {
    const words = text.split(" ")
    let currentText = ""

    for (let i = 0; i < words.length; i++) {
      currentText += (i === 0 ? "" : " ") + words[i]
      setMessages((prev) =>
        prev.map((msg, idx) => (idx === messageIndex ? { ...msg, text: currentText } : msg))
      )
      await new Promise((resolve) => setTimeout(resolve, 50))
    }
  }

  const sendMessage = async (messageText?: string) => {
    const textToSend = messageText || chatInput
    if (!textToSend.trim()) return

    const now = new Date()
    const timestamp = now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })

    const newMessage = {
      sender: "user" as const,
      text: textToSend,
      timestamp,
    }
    setMessages((prev) => [...prev, newMessage])
    setShowOptions(false)

    const payload = {
      user_id: userId,
      essay_id,
      errors: [errorSnippet],
      competency,
      message: textToSend,
    }

    setLoading(true)

    const typingMessage = {
      sender: "tutor" as const,
      text: "",
      isTyping: true,
    }
    setMessages((prev) => [...prev, typingMessage])

    try {
      const idToken = await auth?.currentUser?.getIdToken()
      if (!idToken) {
        throw new Error("Sessão expirada. Faça login novamente.")
      }
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/intelligence/tutor`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify(payload),
      })
      const data = await response.json()
      console.log("Resposta do tutor:", data)
      const tutorReply =
        Array.isArray(data) && data.length > 0 && data[0].response
          ? data[0].response
          : "Desculpe, não entendi."

      setMessages((prev) => {
        const newMessages = prev.filter((msg) => !msg.isTyping)
        const newMessageIndex = newMessages.length
        const newTutorMessage = {
          sender: "tutor",
          text: "",
          timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
        }
        setTimeout(() => animateText(tutorReply, newMessageIndex), 0)
        return [...newMessages, newTutorMessage]
      })
    } catch (err) {
      console.error("Erro ao enviar mensagem para tutor:", err)
      setMessages((prev) => {
        const newMessages = prev.filter((msg) => !msg.isTyping)
        return [
          ...newMessages,
          {
            sender: "tutor",
            text: "Houve um erro ao enviar sua mensagem.",
            timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
          },
        ]
      })
    } finally {
      setLoading(false)
      setChatInput("")
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  
  const renderOptions = () => {
    if (!showOptions) return null
    return (
      <div className={styles.optionsContainer}>
       
     
        <button
          className={styles.optionButton}
          onClick={() => sendMessage("Não entendi o erro.")}
        >
          Não entendi o erro.
        </button>
        <button className={styles.optionButton} onClick={() => sendMessage("Quero mais detalhes sobre a teoria")}>
        Quero mais detalhes sobre a teoria.
        </button>
        <button className={styles.optionButton} onClick={() => sendMessage("Me dê outra sugestão de correção")}>
          Me dê outra sugestão de correção.
        </button>
      </div>
    )
  }

  return (
    <div className={styles.chatWidget}>
      <div className={styles.borderCtn}>
        <div className={styles.header}>
          <div className={styles.headerTitle}>Redator</div>
          <button onClick={onClose} className={styles.closeButton}>
            X
          </button>
        </div>
        <div className={styles.messages}>
          {messages.map((msg, index) => (
            <div key={index} className={msg.sender === "user" ? styles.userMessage : styles.tutorMessage}>
              <div className={styles.messageTitle}>{msg.sender === "user" ? "" : "Redator"}</div>
              <div className={styles.messageText}>
                {msg.isTyping ? (
                  <div className={styles.typingIndicator}>
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                ) : (
                  msg.text
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        {renderOptions()}
        <div className={styles.inputContainer}>
          <textarea
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Escreva sua mensagem..."
            disabled={loading}
            onKeyDown={handleKeyDown}
          />
          <button onClick={() => sendMessage()} disabled={loading}>
            📤
          </button>
        </div>
      </div>
    </div>
  )
}
