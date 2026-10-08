# 🚀 Publicando o Ingressou na internet (Render, plano gratuito)

Tempo estimado: 20 minutos. Você só precisa de uma conta no GitHub e uma no Render.

## Passo 1 — Colocar o código no GitHub

1. Crie uma conta em https://github.com (grátis)
2. Crie um repositório **privado** chamado `ingressou`
3. No terminal, dentro da pasta do projeto:

```bash
git init
git add .
git commit -m "Ingressou — versão inicial"
git remote add origin https://github.com/SEU-USUARIO/ingressou.git
git push -u origin main
```

> ⚠️ O arquivo `.env` **não** vai para o GitHub (já está no `.gitignore`) — suas senhas ficam seguras.

## Passo 2 — Criar o serviço no Render

1. Crie uma conta em https://render.com (grátis, pode entrar com o GitHub)
2. No painel: **New → Blueprint** → conecte o repositório `ingressou`
3. O Render lê o arquivo `render.yaml` e cria automaticamente:
   - o site (web service)
   - o banco PostgreSQL
   - a `SECRET_KEY` segura gerada sozinha
4. Clique em **Deploy** e aguarde (~5 minutos)

## Passo 3 — Ajustar o endereço

O Render te dá um endereço tipo `https://ingressou-abcd.onrender.com`.
No painel do Render → **Environment**, ajuste as 3 variáveis para esse endereço:

```
ALLOWED_HOSTS=ingressou-abcd.onrender.com
SITE_URL=https://ingressou-abcd.onrender.com
CSRF_TRUSTED_ORIGINS=https://ingressou-abcd.onrender.com
```

## Passo 4 — Criar seu usuário admin (com senha forte!)

No painel do Render → **Shell** do serviço:

```bash
python manage.py createsuperuser
```

Use uma senha forte — esta é a porta do seu painel financeiro.

## Passo 5 — Cadastrar os eventos de verdade

Acesse `https://seu-endereco.onrender.com/admin/`, apague os eventos de
demonstração e cadastre os reais (com fotos de capa).

## Depois (quando quiser)

- **Domínio próprio** (`ingressou.com.br`): compre no Registro.br e aponte no Render → Settings → Custom Domains (grátis, HTTPS automático)
- **Mercado Pago real**: preencha `MP_ACCESS_TOKEN` nas variáveis de ambiente do Render
- **E-mail real**: configure as variáveis `EMAIL_*` (ver `.env.example`)

## ⚠️ Limitações do plano gratuito (importante saber)

| Item | Limitação | Solução quando crescer |
|------|-----------|------------------------|
| Banco PostgreSQL grátis | Expira após 30 dias (aviso por e-mail, dá para renovar/migrar) | Plano pago (~US$ 7/mês) |
| Fotos de capa e QR codes | O disco do plano grátis zera a cada deploy | Cloudinary (grátis) ou disco persistente |
| Site "dorme" | Após 15 min sem acesso, o primeiro acesso demora ~30s | Plano pago ou ping de monitoramento |

Os **dados de vendas ficam no PostgreSQL** — o disco temporário só afeta imagens,
e os QR codes são regerados a cada deploy se necessário (o código do ingresso está no banco).
