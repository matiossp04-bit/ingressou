# Ingressou 🎟️

Plataforma de venda de ingressos (estilo Sympla) em Django + Python.

## Como rodar

```bash
# 1. Ativar o ambiente virtual (Windows/Git Bash)
.venv/Scripts/activate

# 2. Subir o site
python manage.py runserver
# ou na porta de preview:
python dev.py --port 7100
```

Acesse:

- **Loja:** http://localhost:8000/
- **Admin (cadastrar eventos/produtores):** http://localhost:8000/admin/
- **Painel financeiro:** http://localhost:8000/painel/
- Login de demonstração: usuário `admin`, senha `ingressou123` (**troque antes de publicar!**)

## Como funciona o dinheiro

```
Ingresso do produtor (preço exato que ele definiu)   R$ 100,00
+ Taxa de serviço Ingressou (17%)                    R$  17,00
= Total pago pelo comprador                          R$ 117,00

Custos descontados da taxa do Ingressou:
− Taxa do Mercado Pago (Pix 0,99% / Cartão 4,99% sobre o total)
− Imposto do Ingressou (15% sobre a taxa de serviço)

= Lucro líquido do Ingressou (visível no /painel/)

Repasse ao produtor: exatamente R$ 100,00 por ingresso.
Os impostos da parte do produtor são responsabilidade dele.
```

Todas as alíquotas são configuráveis no admin em **Configuração da plataforma**.

## Ativando o Mercado Pago (quando quiser cobrar de verdade)

1. Crie uma aplicação em https://www.mercadopago.com.br/developers/panel/app
2. Copie `.env.example` para `.env` e preencha `MP_ACCESS_TOKEN` e `MP_PUBLIC_KEY`
3. Ajuste `SITE_URL` para o endereço público do site (necessário para o webhook)
4. Pronto — o checkout passa a redirecionar para o Mercado Pago automaticamente,
   e a confirmação chega pelo webhook em `/pagamentos/webhook/`

Enquanto o `.env` estiver vazio, o site roda em **modo simulado** (botões de teste
na tela de pagamento) — perfeito para testar todo o fluxo.

## Tarefas de manutenção

```bash
# Devolver ao estoque os ingressos de pedidos não pagos e vencidos
python manage.py expirar_pedidos
```

## Estrutura

```
eventos/    → eventos, produtores, tipos de ingresso, configurações
pedidos/    → checkout, pagamento (Mercado Pago), ingressos com QR code
painel/     → dashboard financeiro do administrador
templates/  → páginas do site
```
