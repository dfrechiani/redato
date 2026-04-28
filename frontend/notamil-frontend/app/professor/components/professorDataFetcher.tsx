'use client';

import { useEffect, useState, useRef } from 'react';

// Interface para a lista de turmas
interface ClassInfo {
  id: string;
  name: string;
  average_grade?: string | number;
}

/**
 * Componente para buscar dados das turmas do professor
 * Não renderiza nenhum elemento visível, apenas faz requisições e envia os dados via callbacks
 */
export default function ProfessorDataFetcher({ 
  onClassesLoaded,
  onClassDataLoaded,
  classId,
  disabled = false
}: { 
  onClassesLoaded?: (classes: ClassInfo[]) => void;
  onClassDataLoaded?: (classData: any) => void;
  classId?: string;
  disabled?: boolean; // Nova prop para controlar se o componente deve fazer requisições
}) {
  const [isLoading, setIsLoading] = useState(true);
  // Este ref garantirá que a requisição para listar turmas seja feita apenas uma vez
  const hasFetchedData = useRef(false);
  // Este ref mantém o controle do último classId processado
  const lastProcessedClassId = useRef<string | null>(null);
  
  // Efeito para buscar lista de turmas ao iniciar o componente
  useEffect(() => {
    // Se disabled for true, não fazer requisições
    if (disabled) return;
    
    // Recupera o user_id do localStorage
    const userId = localStorage.getItem("user_id");
    
    // Se já buscou dados ou não tem userId, não faz nada
    if (hasFetchedData.current || !userId) {
      return;
    }
    
    // Marca que já iniciou a busca
    hasFetchedData.current = true;
    
    console.log("🔑 Iniciando busca de dados com User ID:", userId);
    
    // Buscar lista de turmas do professor
    const fetchGeneralProfessorData = async () => {
      const endpoint = '/dashboard/general/professor';
      
      // Parâmetros para a busca de turmas
      const params = `user_id=${userId}&professor_id=${userId}`;
      const fullUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL}${endpoint}?${params}`;
      
      try {
        console.log(`📡 Buscando dados de turmas: ${fullUrl}`);
        
        const response = await fetch(fullUrl, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });
        
        console.log(`Status: ${response.status} para ${endpoint}`);
        
        if (!response.ok) {
          let errorText = '';
          try {
            const errorData = await response.json();
            errorText = JSON.stringify(errorData);
          } catch (e) {
            errorText = `${response.status} ${response.statusText}`;
          }
          
          console.error(`❌ Erro na resposta (${endpoint}): ${errorText}`);
          return;
        }
        
        const data = await response.json();
        console.log(`✅ Dados recebidos de ${endpoint}:`, data);
        
        // Se tiver um callback para fornecer as classes, processar os dados e chamar
        if (onClassesLoaded && data && data.data && Array.isArray(data.data)) {
          const classes = data.data.map((cls: any) => ({
            id: cls.id || '',
            name: cls.name || 'Turma sem nome',
            average_grade: cls.average_grade || ''
          }));
          
          console.log('👨‍👩‍👧‍👦 Turmas encontradas:', classes);
          onClassesLoaded(classes);
        }
      } catch (error: any) {
        console.error(`❌ Erro em ${endpoint}:`, error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchGeneralProfessorData();
    
  }, [disabled, onClassesLoaded]); // Adicionamos disabled como dependência
  
  // Efeito para buscar dados específicos da turma quando o classId mudar
  useEffect(() => {
    // Se disabled for true, não fazer requisições
    if (disabled) return;
    
    // Se não temos um classId ou já processamos este classId, não faz nada
    if (!classId || classId === lastProcessedClassId.current) {
      return;
    }
    
    console.log(`🔍 Nova busca para turma ID: ${classId}`);
    lastProcessedClassId.current = classId;
    
    const fetchClassData = async () => {
      // Buscar dados dos alunos da turma
      const endpointStudents = '/dashboard/class';
      const paramsStudents = `class_id=${classId}`;
      const urlStudents = `${process.env.NEXT_PUBLIC_API_BASE_URL}${endpointStudents}?${paramsStudents}`;
      
      // Buscar dados de competências da turma
      const endpointCompetencies = '/dashboard/competency/class';
      const paramsCompetencies = `class_id=${classId}`;
      const urlCompetencies = `${process.env.NEXT_PUBLIC_API_BASE_URL}${endpointCompetencies}?${paramsCompetencies}`;
      
      try {
        console.log(`📡 Buscando dados dos alunos: ${urlStudents}`);
        console.log(`📡 Buscando dados de competências: ${urlCompetencies}`);
        
        // Executar as duas requisições em paralelo
        const [responseStudents, responseCompetencies] = await Promise.all([
          fetch(urlStudents, {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              "accept": "application/json"
            }
          }),
          fetch(urlCompetencies, {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              "accept": "application/json"
            }
          })
        ]);
        
        // Verificar e processar resposta de alunos
        if (!responseStudents.ok) {
          throw new Error(`Erro ao buscar dados dos alunos: ${responseStudents.status}`);
        }
        
        const studentsData = await responseStudents.json();
        console.log("✅ Dados dos alunos recebidos:", studentsData);
        
        // Verificar e processar resposta de competências
        if (!responseCompetencies.ok) {
          throw new Error(`Erro ao buscar dados de competências: ${responseCompetencies.status}`);
        }
        
        const competenciesData = await responseCompetencies.json();
        console.log("✅ Dados de competências recebidos:", competenciesData);
        
        // Combinar os dados para o callback
        const combinedData = {
          students: studentsData,
          competencies: competenciesData
        };
        
        // Notificar o componente pai
        if (onClassDataLoaded) {
          onClassDataLoaded(combinedData);
        }
      } catch (error: any) {
        console.error(`❌ Erro ao buscar dados da turma: ${error.message}`);
        
        // Mesmo em caso de erro, notificar o componente pai para encerrar o loading
        if (onClassDataLoaded) {
          onClassDataLoaded({ error: error.message });
        }
      }
    };
    
    fetchClassData();
  }, [classId, onClassDataLoaded, disabled]); // Adicionamos disabled como dependência
  
  // Método para resetar o estado do componente ao trocar de turma
  const resetLastProcessedClassId = () => {
    lastProcessedClassId.current = null;
  };
  
  // Não renderiza nada visível, retorna null
  return null;
}