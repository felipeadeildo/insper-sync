# 📅 Insper Sync

**Nunca mais perca uma aula, prova ou evento do Insper!**

<div align="center">

![Insper Sync Demo](https://img.shields.io/badge/Status-Ativo-brightgreen)
![Usuários](https://img.shields.io/badge/Estudantes-100%25%20Gratuito-blue)
![Segurança](https://img.shields.io/badge/Segurança-Máxima-green)

</div>

## 🎯 O que é?

O **Insper Sync** é um serviço gratuito que sincroniza automaticamente seu calendário acadêmico do Insper com o Google Calendar. 

**Em outras palavras**: Suas aulas, provas e eventos aparecem automaticamente no calendário do seu celular, sem você precisar fazer nada! 📱✨

## ❓ Por que usar?

### Antes do Insper Sync:
- 😤 Ficar checando o portal acadêmico toda hora
- 📝 Copiar eventos manualmente para o seu calendário
- 😱 Descobrir que tinha prova só no dia
- 📱 Calendário vazio no celular

### Depois do Insper Sync:
- 🎉 Tudo aparece automaticamente no seu Google Calendar
- 📲 Notificações no celular sobre próximos eventos
- ⏰ Lembretes automáticos de provas e aulas
- 🔄 Sempre atualizado, sem esforço nenhum

## 🚀 Como funciona?

```mermaid
graph TB
    subgraph "🎓 Estudante"
        A[📧 Email @al.insper.edu.br]
        B[🔑 Credenciais Portal]
        C[📱 Google Account]
    end
    
    subgraph "🔐 Insper Sync - Autenticação"
        D[✉️ Token por Email]
        E[🛡️ Criptografia RSA]
        F[🔗 OAuth Google]
    end
    
    subgraph "🏫 Portal Acadêmico Insper"
        G[🌐 Sistema SGA]
        H[📅 API de Eventos]
        I[📚 Aulas, Provas, Seminários]
    end
    
    subgraph "⚙️ Processamento Automático"
        J[🔄 Celery Worker]
        K[🕒 Agendador - A cada 6h]
        L[🔍 Busca Novos Eventos]
        M[📝 Formata Dados]
        N[🎯 Aplica Filtros]
    end
    
    subgraph "☁️ Google Calendar"
        O[📅 Calendar API]
        P[➕ Criar Eventos]
        Q[✏️ Atualizar Eventos]
        R[🗑️ Remover Eventos]
    end
    
    subgraph "📱 Dispositivos do Estudante"
        S[📱 Celular]
        T[💻 Computador]
        U[⌚ Smartwatch]
        V[🔔 Notificações]
    end
    
    %% Fluxo de Autenticação
    A -->|1. Login| D
    D -->|2. Verifica| A
    B -->|3. Criptografa| E
    C -->|4. Autoriza| F
    
    %% Fluxo de Sincronização
    E -->|5. Login Seguro| G
    G -->|6. Acessa| H
    H -->|7. Retorna| I
    
    %% Processamento
    K -->|8. Dispara| J
    J -->|9. Busca| L
    L -->|10. Consulta| H
    I -->|11. Dados Brutos| M
    M -->|12. Eventos Formatados| N
    N -->|13. Eventos Filtrados| O
    
    %% Sincronização Google
    O -->|14. Cria| P
    O -->|15. Atualiza| Q
    O -->|16. Remove| R
    
    %% Entrega Final
    P -->|17. Sincroniza| S
    Q -->|18. Atualiza| T
    R -->|19. Remove| U
    S -->|20. Gera| V
    
    %% Estilos
    classDef student fill:#e3f2fd,stroke:#1976d2
    classDef auth fill:#f3e5f5,stroke:#7b1fa2
    classDef insper fill:#e8f5e8,stroke:#388e3c
    classDef process fill:#fff3e0,stroke:#f57c00
    classDef google fill:#ffebee,stroke:#d32f2f
    classDef devices fill:#f1f8e9,stroke:#689f38
    
    class A,B,C student
    class D,E,F auth
    class G,H,I insper
    class J,K,L,M,N process
    class O,P,Q,R google
    class S,T,U,V devices
```

### É super simples:

1. **📧 Faça login** com seu email do Insper
2. **🔑 Configure** suas credenciais do portal (100% seguro!)
3. **🔗 Conecte** com seu Google Calendar
4. **✨ Pronto!** Seus eventos aparecem automaticamente

## 🛡️ É seguro?

**Absolutamente!** Sua segurança é nossa prioridade:

- 🔐 **Criptografia militar**: Sua senha é criptografada com a chave oficial do Insper
- 👀 **Nem nós vemos sua senha**: Impossível para qualquer pessoa acessar
- 🎓 **Só estudantes**: Apenas emails @al.insper.edu.br são aceitos
- 🗑️ **Controle total**: Você pode deletar tudo a qualquer momento

## ⚡ Funcionalidades Incríveis

### 🎨 **Personalizável**
- Escolha quais tipos de eventos sincronizar
- Adicione ou remova o prefixo "[Insper]"
- Configure a frequência de atualização

### 📊 **Inteligente**
- Detecta automaticamente mudanças de horário
- Remove eventos cancelados
- Atualiza informações de professores e salas

### 📱 **Funciona em tudo**
- Celular Android e iPhone
- Tablet e computador
- Apple Watch e smartwatches
- Qualquer app que use Google Calendar

## 🎯 Perfeito para:

- **📚 Calouros**: Que ainda estão se organizando
- **🎓 Veteranos**: Que querem mais praticidade  
- **📱 Viciados em tecnologia**: Que amam automação
- **🤯 Esquecidos**: Que vivem perdendo prazos
- **📅 Organizados**: Que querem tudo centralizado


## 📱 Como começar?

É literalmente mais fácil que pedir um Uber:

1. **Acesse**: [sync.insper.dev](https://sync.insper.dev)
2. **Digite**: Seu email @al.insper.edu.br
3. **Confirme**: Token enviado por email
4. **Configure**: Credenciais do portal (super seguro)
5. **Conecte**: Seu Google Calendar
6. **🎉 Pronto!**: Relaxa e deixa a mágica acontecer

## ❓ Dúvidas Frequentes

<details>
<summary><strong>💰 É realmente gratuito?</strong></summary>

Sim! 100% gratuito, sem pegadinhas. É um projeto feito por estudantes para estudantes.
</details>

<details>
<summary><strong>🔒 Minha senha está segura?</strong></summary>

Mais segura que no próprio Insper! Usamos criptografia militar e nem nós conseguimos ver sua senha.
</details>

<details>
<summary><strong>📱 Funciona no iPhone?</strong></summary>

Perfeitamente! Funciona em qualquer dispositivo que tenha Google Calendar.
</details>

<details>
<summary><strong>⏰ Com que frequência atualiza?</strong></summary>

A cada 6 horas por padrão, mas você pode configurar de 1 hora até 1 dia.
</details>

<details>
<summary><strong>🗑️ Como cancelo?</strong></summary>

Super fácil! Basta entrar no painel e clicar em "Deletar conta". Tudo é removido instantaneamente.
</details>

## 🆘 Precisa de ajuda?

- **💬 Dúvidas**: [fa@insper.dev](mailto:fa@insper.dev)
- **🐛 Problemas**: [Reportar aqui](https://github.com/felipeadeildo/insper-sync/issues)
- **💡 Sugestões**: Manda um email que adoramos feedback!

---

<div align="center">

**🎓 Feito por estudantes, para estudantes do Insper**

**[🚀 Começar agora - É grátis!](https://sync.insper.dev)**

*Não é afiliado oficialmente ao Insper*

</div>