import logging
import asyncio
import re
import os
import requests
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Configuração inicial
TOKEN = os.getenv("TELEGRAM_TOKEN")
JWT_TOKEN = os.getenv("JWT_TOKEN")  # Pix2Depix token
CREDENTIALS_JSON = os.getenv("CREDENTIALS_JSON")  # Google Sheets credentials
BTC_API_URL = "https://economia.awesomeapi.com.br/json/last/BTC-BRL"
API_URL = "https://depix.eulen.app/api/deposit"
STATUS_URL = "https://depix.eulen.app/api/deposit-status"
ADMIN_ID = 00000000  # Substitua pelo seu ID de administrador
MAX_REQUESTS_PER_MINUTE = 2  # Limite de 2 solicitações por minuto

# Verifica se as variáveis de ambiente estão definidas
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN não está definido. Configure a variável de ambiente.")
if not JWT_TOKEN:
    raise ValueError("JWT_TOKEN não está definido. Configure a variável de ambiente.")
if not CREDENTIALS_JSON:
    raise ValueError("CREDENTIALS_JSON não está definido. Configure a variável de ambiente.")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Estruturas para rate limiting e transações pendentes
user_requests = defaultdict(list)  # Armazena timestamps das solicitações por usuário
pending_transactions = {}  # Armazena transações pendentes até confirmação

# Headers para chamadas de API
HEADERS = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json",
    "X-Async": "auto",
}

# Estados para o FSM (Finite State Machine)
class Form(StatesGroup):
    amount = State()
    address = State()

# Função para conectar ao Google Sheets
def get_google_sheet():
    creds_dict = json.loads(CREDENTIALS_JSON)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("DefinityDepixDeposits").sheet1  # Nome da planilha
    return sheet

# Função de rate limiting
def rate_limit(user_id):
    now = datetime.now()
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < timedelta(minutes=1)]
    if len(user_requests[user_id]) >= MAX_REQUESTS_PER_MINUTE:
        return False
    user_requests[user_id].append(now)
    return True

# Função para gerar QR code Pix
async def generate_pix_qr(amount):
    payload = {"amountInCents": amount * 100}
    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=10)
        data = response.json()
        if response.status_code == 200 and not data.get("async"):
            return data["response"]
        else:
            raise Exception(f"Erro na API: {data.get('response', {}).get('errorMessage', 'Unknown')}")
    except Exception as e:
        logger.error(f"Erro ao gerar QR code: {e}")
        raise

# Função para verificar status de pagamento em segundo plano
async def check_payment_status():
    while True:
        for deposit_id, transaction in list(pending_transactions.items()):
            try:
                response = requests.get(f"{STATUS_URL}?id={deposit_id}", headers=HEADERS, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    status = data["response"]["status"]
                    if status == "depix_sent":
                        # Exportar para Google Sheets
                        sheet = get_google_sheet()
                        sheet.append_row([
                            str(transaction["user_id"]),
                            transaction["amount"],
                            deposit_id,
                            transaction["btc_address"],
                            transaction["timestamp"]
                        ])
                        # Mensagem para o usuário
                        await bot.send_message(
                            transaction["user_id"],
                            "✅ Pix recebido! Em breve, você receberá o hash da transação Bitcoin."
                        )
                        # Mensagem para o admin
                        await bot.send_message(
                            ADMIN_ID,
                            f"✅ Pagamento confirmado:\n"
                            f"👤 Usuário ID: {transaction['user_id']}\n"
                            f"💵 Valor: R$ {transaction['amount']}\n"
                            f"📜 Deposit ID: {deposit_id}\n"
                            f"🏦 Endereço BTC: {transaction['btc_address']}\n"
                            f"⏰ Data e hora: {transaction['timestamp']}\n"
                            f"Prossiga com o envio do Bitcoin."
                        )
                        del pending_transactions[deposit_id]
            except Exception as e:
                logger.error(f"Erro ao verificar status da transação {deposit_id}: {e}")
        await asyncio.sleep(30)  # Verifica a cada 30 segundos

# Comando /start
@dp.message(Command("start"))
async def start(message: types.Message):
    logger.info("Comando /start recebido")
    await message.answer(
        "🚨 Horário de Atendimento 🚨\n\n"
        "Prezado cliente,\n"
        "Nosso horário de atendimento para suporte é das 10h às 20h (de segunda a sexta). "
        "Aos finais de semana, o atendimento acontece conforme a disponibilidade dos atendentes.\n"
        "Respondemos sempre o mais breve possível!"
    )
    await asyncio.sleep(1)
    await message.answer(
        "🔹 Como funciona a Definity?\n\n"
        "A Definity foi criada para que você possa comprar Bitcoin de forma segura, privada e eficiente, "
        "sem depender de bancos ou governos. Utilizamos tecnologias que garantem transações rápidas e protegidas, "
        "proporcionando total controle sobre seus fundos.\n\n"
        "🛠 Passo 1: Escolha o valor que deseja comprar\n"
        "• Informe o valor em reais que deseja converter para Bitcoin.\n"
        "• Você pode comprar entre R$ 20 e R$ 6000 por dia, respeitando o limite diário por CPF.\n"
        "• Após isso, você receberá um resumo da conversão, incluindo a cotação do BTC e as taxas aplicáveis.\n\n"
        "🏦 Passo 2: Efetue o pagamento via Pix\n"
        "• O sistema gera uma chave Pix exclusiva para sua compra.\n"
        "• Realize o pagamento dentro do prazo indicado para garantir a cotação informada.\n"
        "• Assim que o pagamento for detectado, a transação será processada.\n\n"
        "📤 Passo 3: Informe seu endereço de Bitcoin\n"
        "• Após o pagamento, forneça um endereço de carteira Bitcoin para receber os fundos.\n"
        "• Certifique-se de que o endereço está correto, pois as transações são irreversíveis.\n"
        "• Carteira recomendada para iniciantes: Sugerimos o uso da Blue Wallet (offline), "
        "uma opção segura e fácil de usar que garante controle total sobre seus ativos.\n\n"
        "🔎 Passo 4: Receba seus Bitcoins\n"
        "• Após a confirmação, seus Bitcoins serão enviados diretamente para sua carteira.\n"
        "• O tempo de recebimento pode variar conforme a velocidade da rede e a taxa de transação escolhida.\n\n"
        "🚀 Por que usar a Definity?\n"
        "• Privacidade: Nenhum dado pessoal é solicitado, garantindo anonimato total.\n"
        "• Rapidez: As transações são concluídas rapidamente após a confirmação do pagamento.\n"
        "• Segurança: Nosso sistema opera com máxima proteção para que você receba seus fundos sem riscos.\n"
        "• Independência financeira: Retire seu dinheiro do sistema tradicional e tenha controle total sobre seu patrimônio.\n\n"
        "🔐 Compre Bitcoin de forma segura e sem burocracia com a Definity!"
    )
    await asyncio.sleep(1)
    await message.answer("Ao usar a Definity, você concorda com nossos termos de uso.")
    await asyncio.sleep(1)
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Tenho um código para colar", callback_data="colar_codigo")],
        [InlineKeyboardButton(text="📥 Comprar Bitcoin", callback_data="comprar")],
        [InlineKeyboardButton(text="ℹ️ Sobre a plataforma", callback_data="sobre")],
        [InlineKeyboardButton(text="📞 Falar com suporte", callback_data="suporte")]
    ])
    await message.answer("Escolha uma opção abaixo:", reply_markup=buttons)

# Comando /notify (restrito ao admin)
@dp.message(Command("notify"))
async def notify(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Este comando é restrito ao administrador.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Uso: /notify <user_id> [mensagem]\nExemplo: /notify 123456789 Olá!")
        return
    try:
        user_id = int(parts[1])
        msg = parts[2] if len(parts) > 2 else "Mensagem padrão"
        await bot.send_message(user_id, msg)
        await message.answer(f"Mensagem enviada para o usuário com ID {user_id}.")
    except Exception as e:
        logger.error(f"Erro ao enviar notificação: {e}")
        await message.answer(f"Erro: {e}. Certifique-se de que o usuário interagiu com o bot.")

# Botão "Comprar Bitcoin"
@dp.callback_query(lambda query: query.data == "comprar")
async def comprar_bitcoin(query: types.CallbackQuery, state: FSMContext):
    logger.info("Botão 'Comprar Bitcoin' clicado")
    await state.set_state(Form.amount)
    await query.message.answer(
        "Digite a quantia desejada, apenas em números de 20 a 6000 (limite diário por CPF), sem vírgula ou pontuações."
    )
    await query.answer()

# Botão "Tenho um código para colar"
@dp.callback_query(lambda query: query.data == "colar_codigo")
async def colar_codigo(query: types.CallbackQuery, state: FSMContext):
    logger.info("Botão 'Tenho um código para colar' clicado")
    await state.set_state(Form.amount)
    await query.message.answer("Copie o código de compra gerado no site no chat e envie agora.")
    await query.answer()

# Processa a quantia ou código
@dp.message(StateFilter(Form.amount))
async def process_amount_or_code(message: types.Message, state: FSMContext):
    logger.info(f"Processando entrada: {message.text}")
    text = message.text

    code_match = re.search(r"SHA256(\d+)DEFINITY\.SPACE", text)
    if code_match:
        amount = int(code_match.group(1))
    elif text.isdigit():
        amount = int(text)
    else:
        await message.answer(
            "Entrada inválida. Forneça um código de compra válido ou uma quantia em números de 20 a 6000."
        )
        return

    if 20 <= amount <= 6000:
        await state.update_data(amount=amount)
        try:
            response = requests.get(BTC_API_URL)
            if response.status_code == 200:
                data = response.json()
                btc_price = float(data["BTCBRL"]["bid"])
                definity_fee = round(amount * 0.02, 2)
                network_fee_usd = "aprox. 0,50 a 2,50 USD"
                btc_amount = ((amount * 0.98) - 10) / btc_price
                formatted_btc_amount = f"{btc_amount:.8f}"  # Formata para 8 casas decimais como decimal
                formatted_btc_price = f"{btc_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                await message.answer(
                    f"💵 Valor escolhido: R$ {amount}\n"
                    f"💰 Cotação atual: 1 BTC é aprox. R$ {formatted_btc_price}\n"
                    f"📉 Tarifa Definity: 2%\n"
                    f"🔗 Taxa da rede: {network_fee_usd}\n"
                    f"📤 Você receberá aproximadamente {formatted_btc_amount} BTC."
                )
                await state.set_state(Form.address)
                await message.answer(
                    "Por favor, forneça seu endereço de Bitcoin. Certifique-se de que começa com 'bc1', '1' ou '3'."
                )
            else:
                raise Exception(f"Erro na API: status {response.status_code}")
        except Exception as e:
            logger.error(f"Erro na API BTCBRL: {e}")
            await message.answer("❌ Erro ao obter a cotação do Bitcoin. Tente novamente mais tarde.")
            await state.clear()
    else:
        await message.answer("O valor deve estar entre R$ 20 e R$ 6000. Tente novamente.")

# Processa o endereço BTC
@dp.message(StateFilter(Form.address))
async def process_address(message: types.Message, state: FSMContext):
    logger.info(f"Endereço BTC recebido: {message.text}")
    address = message.text
    if re.match(r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$', address):
        user_data = await state.get_data()
        amount = user_data["amount"]
        user_id = message.from_user.id

        # Verificar rate limiting
        if not rate_limit(user_id):
            await message.answer("⏳ Você atingiu o limite de solicitações. Tente novamente em um minuto.")
            return

        try:
            qr_data = await generate_pix_qr(amount)
            qr_url = qr_data["qrImageUrl"]
            qr_copy_paste = qr_data["qrCopyPaste"]
            deposit_id = qr_data["id"]
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            await message.answer_photo(
                photo=qr_url,
                caption=f"Use o QR code acima ou copie o código Pix abaixo para pagar R$ {amount}:"
            )
            await message.answer(f"```\n{qr_copy_paste}\n```", parse_mode="MarkdownV2")

            username = message.from_user.username or "Sem username"
            username_link = f"t.me/{username}" if message.from_user.username else "Sem link"
            await bot.send_message(
                ADMIN_ID,
                f"🚀 Nova solicitação de compra:\n"
                f"👤 Usuário: @{username} ({message.from_user.first_name})\n"
                f"💵 Valor: R$ {amount}\n"
                f"🏦 Endereço BTC: {address}\n"
                f"📲 Contato: {username_link}\n"
                f"📱 ID do usuário: {user_id}\n"
                f"🔢 Deposit ID: {deposit_id}"
            )

            # Armazenar transação pendente
            pending_transactions[deposit_id] = {
                "user_id": user_id,
                "amount": amount,
                "btc_address": address,
                "timestamp": timestamp
            }
        except Exception as e:
            logger.error(f"Erro ao gerar QR code: {e}")
            await message.answer("❌ Erro ao gerar o QR code. Tente novamente mais tarde.")
        await state.clear()
    else:
        await message.answer("Endereço BTC inválido. Deve começar com 'bc1', '1' ou '3'.")

# Botão "Suporte"
@dp.callback_query(lambda query: query.data == "suporte")
async def suporte(query: types.CallbackQuery):
    logger.info("Botão 'Suporte' clicado")
    username = query.from_user.username or "Sem username"
    username_link = f"t.me/{username}" if query.from_user.username else "Sem link"
    await bot.send_message(
        ADMIN_ID,
        f"📞 Novo pedido de suporte\n"
        f"👤 Usuário: @{username} ({query.from_user.first_name})\n"
        f"📲 Contato: {username_link}\n"
        f"📱 ID: {query.from_user.id}"
    )
    await query.message.answer("📞 Sua solicitação de suporte foi enviada. Aguarde contato.")
    await query.answer()

# Botão Sobre (unchanged)
@dp.callback_query(lambda query: query.data == "sobre")
async def sobre(query: types.CallbackQuery):
    logger.info("Botão 'Sobre' clicado")
    await query.message.answer("ℹ️ A Definity é uma plataforma projetada para permitir a compra de Bitcoin de forma segura, privada e eficiente, sem intermediários ou burocracia. Nosso sistema utiliza tecnologias avançadas para garantir transações rápidas e protegidas, assegurando que você tenha total controle sobre seus fundos. Com a Definity, você pode adquirir Bitcoin anonimamente, sem precisar compartilhar dados pessoais ou enfrentar restrições bancárias. Nossa missão é fortalecer a soberania financeira dos usuários, proporcionando uma alternativa confiável e acessível ao sistema financeiro tradicional.")
    await asyncio.sleep(1)
    site_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Visite nosso site", url="https://definity.space")]
    ])
    await query.message.answer("Confira mais detalhes no nosso site oficial!", reply_markup=site_button)
    await query.answer()


# Inicia o bot
async def main():
    logger.info("Iniciando o bot...")
    asyncio.create_task(check_payment_status())  # Inicia verificação de status
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
