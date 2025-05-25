# 📅 Insper Sync

Ferramenta para sincronizar calendários do Insper com Google Calendar.

## 🚀 Configuração do Desenvolvimento

### 1. Instalar Dependências

```bash
# Usando uv (recomendado)
uv sync

# Ou usando pip
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

Copie o arquivo de exemplo e configure suas credenciais de email:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações de email:

```env
# Para Gmail (recomendado para desenvolvimento)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app
DEFAULT_FROM_EMAIL=Insper Sync <noreply@inspersync.app>
```

#### Como configurar Gmail:

1. Acesse sua conta Google
2. Ative a verificação em duas etapas
3. Gere uma "Senha de App" específica para esta aplicação
4. Use a senha de app no `EMAIL_HOST_PASSWORD`

### 3. Configurar Banco de Dados

```bash
# Executar migrações
python manage.py migrate

# Criar superusuário (opcional)
python manage.py createsuperuser
```

### 4. Executar o Servidor

```bash
python manage.py runserver
```

A aplicação estará disponível em `http://127.0.0.1:8000/`

## 📧 Configuração de Email

### Desenvolvimento

Por padrão, em modo de desenvolvimento (`DEBUG=True`), os emails são exibidos no console. Para testar com envio real, descomente a linha no `settings.py`:

```python
# Para forçar SMTP mesmo em desenvolvimento, descomente a linha abaixo:
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
```

### Produção

Em produção (`DEBUG=False`), o sistema usa automaticamente o backend SMTP com as configurações das variáveis de ambiente.

### Provedores Suportados

- **Gmail**: `smtp.gmail.com:587` (TLS)
- **Outlook**: `smtp-mail.outlook.com:587` (TLS)
- **Yahoo**: `smtp.mail.yahoo.com:587` (TLS)
- **SendGrid**: `smtp.sendgrid.net:587` (TLS)


## 🔑 Funcionalidades

### ✅ Implementado

- [x] Autenticação baseada em email (apenas domínios @al.insper.edu.br e @insper.edu.br)
- [x] Verificação de email por token
- [x] Interface moderna com daisyUI e Tailwind CSS
- [x] Sistema de temas (claro/escuro)
- [x] Configuração de credenciais do Insper
- [ ] Dashboard básico

### 🚧 Em Desenvolvimento

- [ ] Integração com Google Calendar API
- [ ] Scraping do portal do Insper
- [ ] Sincronização automática de eventos
- [ ] Configurações avançadas de sincronização
- [ ] Notificações por email

## 🛠️ Tecnologias

- **Backend**: Django 5.2
- **Frontend**: daisyUI + Tailwind CSS + Lucide Icons
- **Database**: SQLite (desenvolvimento)
- **Gerenciamento de Pacotes**: uv
- **Email**: SMTP configurável


## 🤝 Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'feat: add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📧 Contato

Para dúvidas ou sugestões, abra uma issue no repositório.