import logging
import asyncio
import re
import os
import requests
import uuid  # Added for generating unique IDs
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Configuração inicial
TOKEN = os.getenv("TELEGRAM_TOKEN")
JWT_TOKEN = os.getenv("JWT_TOKEN")  # New: Get the Pix2Depix token
BTC_API_URL = "https://economia.awesomeapi.com.br/json/last/BTC-BRL"
API_URL = "https://depix.eulen.app/api/deposit"  # Pix2Depix API endpoint
ADMIN_ID = 8025982103

# Verifica se os tokens estão definidos
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN não está definido. Configure a variável de ambiente.")
if not JWT_TOKEN:
    raise ValueError("JWT_TOKEN não está definido. Configure a variável de ambiente.")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)

# Configuração de logs para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definição dos estados para o FSM
class Form(StatesGroup):
    amount = State()  # Estado para entrada da quantia
    address = State()  # Estado para entrada do endereço BTC

# New: Function to generate Pix QR code
async def generate_pix_qr(amount):
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",  # Use the token for authentication
        "Content-Type": "application/json",
        "X-Async": "auto",  # Make the request instant
        "X-Nonce": str(uuid.uuid4())  # Unique ID for each request
    }
    payload = {
        "amountInCents": amount * 100  # Convert reais to centavos (R$ 100 = 10000 cents)
    }
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code == 200 and not data.get("async"):
            return data["response"]  # Contains QR code details
        else:
            raise Exception(f"API Error: {data.get('response', {}).get('errorMessage', 'Unknown')}")
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        raise

# Comando /start (unchanged)
@dp.message(Command("start"))
async def start(message: types.Message):
    logger.info("Comando /start recebido")
    await message.answer("🚨 **Horário de Atendimento** 🚨\n\n"
                         "Prezado cliente,\n"
                         "Nosso horário de atendimento expresso é das 10h às 20h (de segunda a sexta). "
                         "Aos finais de semana, o atendimento acontece conforme a disponibilidade dos atendentes.\n"
                         "Respondemos sempre o mais breve possível!")
    
    await asyncio.sleep(1)

    await message.answer(
        "🔹 **Como funciona a Definity?**\n\n"
        "A **Definity** foi criada para que você possa comprar **Bitcoin de forma segura, privada e eficiente**, "
        "sem depender de bancos ou governos. Utilizamos tecnologias que garantem **transações rápidas e protegidas**, "
        "proporcionando total controle sobre seus fundos.\n\n"
        "🛠 **Passo 1: Escolha o valor que deseja comprar**\n"
        "• Informe o valor em **reais** que deseja converter para Bitcoin.\n"
        "• Você pode comprar entre **R$ 20 e R$ 6000 por dia**, respeitando o limite diário por CPF.\n"
        "• Após isso, você receberá um resumo da conversão, incluindo a cotação do BTC e as taxas aplicáveis.\n\n"
        "🏦 **Passo 2: Efetue o pagamento via Pix**\n"
        "• O sistema gera uma **chave Pix exclusiva** para sua compra.\n"
        "• Realize o pagamento dentro do prazo indicado para garantir a cotação informada.\n"
        "• Assim que o pagamento for detectado, a transação será processada.\n\n"
        "📤 **Passo 3: Informe seu endereço de Bitcoin**\n"
        "• Após o pagamento, forneça um **endereço de carteira Bitcoin** para receber os fundos.\n"
        "• Certifique-se de que o endereço está correto, pois **as transações são irreversíveis**.\n"
        "• **Carteira recomendada para iniciantes:** Sugerimos o uso da **Blue Wallet (offline)**, "
        "uma opção segura e fácil de usar que garante controle total sobre seus ativos.\n\n"
        "🔎 **Passo 4: Receba seus Bitcoins**\n"
        "• Após a confirmação, seus Bitcoins serão enviados diretamente para sua carteira.\n"
        "• O tempo de recebimento pode variar conforme a velocidade da rede e a taxa de transação escolhida.\n\n"
        "🚀 **Por que usar a Definity?**\n"
        "• **Privacidade:** Nenhum dado pessoal é solicitado, garantindo anonimato total.\n"
        "• **Rapidez:** As transações são concluídas rapidamente após a confirmação do pagamento.\n"
        "• **Segurança:** Nosso sistema opera com máxima proteção para que você receba seus fundos sem riscos.\n"
        "• **Independência financeira:** Retire seu dinheiro do sistema tradicional e tenha **controle total sobre seu patrimônio**.\n\n"
        "🔐 **Compre Bitcoin de forma segura e sem burocracia com a Definity!**"
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

# Comando /notify (unchanged)
@dp.message(Command("notify"))
async def notify(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Este comando é restrito ao administrador.")
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) < 2:
        await message.answer("Uso: /notify <user_id> [image_url] [mensagem]\n"
                             "Exemplos:\n"
                             "- Apenas texto: /notify 123456789 Olá, tudo bem?\n"
                             "- Apenas imagem: /notify 123456789 https://exemplo.com/imagem.jpg\n"
                             "- Imagem com texto: /notify 123456789 https://exemplo.com/imagem.jpg Olá!")
        return

    try:
        _, user_id_str = parts[0:2]
        user_id = int(user_id_str)

        if len(parts) == 2:
            second_part = parts[1]
            if re.match(r"^https?://[^\s]+$", second_part):
                await bot.send_photo(chat_id=user_id, photo=second_part)
                await message.answer(f"Imagem enviada para o usuário com ID {user_id}.")
            else:
                await bot.send_message(chat_id=user_id, text=second_part)
                await message.answer(f"Mensagem enviada para o usuário com ID {user_id}.")
        elif len(parts) == 3:
            second_part = parts[1]
            third_part = parts[2]
            if re.match(r"^https?://[^\s]+$", second_part):
                await bot.send_photo(chat_id=user_id, photo=second_part)
                await message.answer(f"Imagem enviada para o usuário com ID {user_id}.")
            else:
                msg = " ".join(parts[1:])
                await bot.send_message(chat_id=user_id, text=msg)
                await message.answer(f"Mensagem enviada para o usuário com ID {user_id}.")
        else:
            image_url = parts[1]
            msg = parts[2]
            if not re.match(r"^https?://[^\s]+$", image_url):
                await message.answer("A URL da imagem não parece válida. Use algo como https://exemplo.com/imagem.jpg")
                return
            await bot.send_photo(chat_id=user_id, photo=image_url, caption=msg)
            await message.answer(f"Imagem com texto enviada para o usuário com ID {user_id}.")

    except ValueError:
        await message.answer("Por favor, forneça um ID válido.\nExemplo: /notify 123456789 Olá!")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para usuário: {e}")
        await message.answer(f"Erro ao enviar mensagem: {e}. Certifique-se de que o usuário interagiu com o bot (e.g., enviou /start).")

# Botão Comprar Bitcoin (unchanged)
@dp.callback_query(lambda query: query.data == "comprar")
async def comprar_bitcoin(query: types.CallbackQuery, state: FSMContext):
    logger.info("Botão 'Comprar Bitcoin' clicado")
    await state.set_state(Form.amount)
    await query.message.answer("Digite a quantia desejada, apenas em números de 20 a 6000 (limite diário por CPF), sem vírgula ou pontuações.")
    await query.answer()

# Botão "Tenho um código para colar" (unchanged)
@dp.callback_query(lambda query: query.data == "colar_codigo")
async def colar_codigo(query: types.CallbackQuery, state: FSMContext):
    logger.info("Botão 'Tenho um código para colar' clicado")
    await state.set_state(Form.amount)
    await query.message.answer("Cole o código de compra gerado no site no chat e envie agora.")
    await query.answer()

# Processa a quantia enviada ou código de compra (unchanged)
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
        await message.answer("Entrada inválida. Forneça um código de compra válido ou uma quantia em números de 20 a 6000 (sem vírgula ou pontuação).")
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
                btc_amount = round(((amount * 0.98) - 10) / btc_price, 8)
                formatted_btc_price = f"{btc_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                await message.answer(
                    f"💵 Valor escolhido: R$ {amount}\n"
                    f"💰 Cotação atual: 1 BTC é aprox. R$ {formatted_btc_price}\n"
                    f"📉 Tarifa Definity: 2%\n"
                    f"🔗 Taxa da rede: {network_fee_usd}\n"
                    f"📤 Você receberá aproximadamente {btc_amount} BTC."
                )
                await state.set_state(Form.address)
                await message.answer("Por favor, forneça seu endereço de Bitcoin. Atente-se para enviar o endereço correto, que geralmente inicia com 'bc1'.")
            else:
                raise Exception(f"Erro na API: status {response.status_code}")
        except Exception as e:
            logger.error(f"Erro na API BTCBRL: {e}")
            await message.answer("❌ Erro ao obter a cotação do Bitcoin. Tente novamente mais tarde.")
            await state.clear()
    else:
        await message.answer("O valor deve estar entre R$ 20 e R$ 6000 (limite diário por CPF). Tente novamente.")

# Processa o endereço BTC (updated with QR code formatting)
@dp.message(StateFilter(Form.address))
async def process_address(message: types.Message, state: FSMContext):
    logger.info(f"Endereço BTC recebido: {message.text}")
    address = message.text
    # Validação básica de endereço BTC
    if re.match(r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$', address):
        user_data = await state.get_data()
        amount = user_data['amount']
        username = message.from_user.username if message.from_user.username else "Sem username"
        username_link = f"t.me/{username}" if message.from_user.username else "Usuário não tem username, peça um contato direto ou use o ID abaixo"

        # Generate the QR code
        try:
            qr_data = await generate_pix_qr(amount)
            qr_url = qr_data["qrImageUrl"]  # URL of the QR code image
            qr_copy_paste = qr_data["qrCopyPaste"]  # Text version of the Pix code
            deposit_id = qr_data["id"]  # Unique ID for this transaction

            # Send QR code image with a short caption
            await message.answer_photo(
                photo=qr_url,
                caption=f"Use o QR code acima ou copie o código Pix abaixo para realizar o pagamento de R$ {amount}:"
            )

            # Send the copy-paste code as a separate message with code block formatting
            await message.answer(
                f"```\n{qr_copy_paste}\n```",
                parse_mode="MarkdownV2"
            )

            # Notify the admin with all details
            await bot.send_message(
                ADMIN_ID,
                f"🚀 Nova solicitação de compra:\n"
                f"👤 Usuário: @{username} ({message.from_user.first_name})\n"
                f"💵 Valor: R$ {amount}\n"
                f"🏦 Endereço BTC: {address}\n"
                f"📲 Contato: {username_link}\n"
                f"📱 ID do usuário: {message.from_user.id}\n"
                f"🔢 ID da transação: {deposit_id}"
            )
        except Exception as e:
            await message.answer("❌ Erro ao gerar o QR code. Tente novamente mais tarde.")
            logger.error(f"Erro ao gerar QR code: {e}")
            # Still notify admin even if QR code fails
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ Nova solicitação de compra (QR code falhou):\n"
                f"👤 Usuário: @{username} ({message.from_user.first_name})\n"
                f"💵 Valor: R$ {amount}\n"
                f"🏦 Endereço BTC: {address}\n"
                f"📲 Contato: {username_link}\n"
                f"📱 ID do usuário: {message.from_user.id}"
            )

        await state.clear()
    else:
        await message.answer("Endereço BTC inválido. Forneça um endereço válido que comece com 'bc1', '1' ou '3'.")

# Botão Suporte (unchanged)
@dp.callback_query(lambda query: query.data == "suporte")
async def suporte(query: types.CallbackQuery):
    logger.info("Botão 'Suporte' clicado")
    username = query.from_user.username if query.from_user.username else "Sem username"
    username_link = f"t.me/{username}" if query.from_user.username else "Usuário não tem username, peça um contato direto ou use o ID abaixo"
    await bot.send_message(
        ADMIN_ID,
        f"📞 **Novo pedido de suporte**\n👤 Usuário: @{username} ({query.from_user.first_name})\n📲 Contato: {username_link}\n📱 ID para envio de mensagem direta: {query.from_user.id}"
    )
    await query.message.answer("📞 Sua solicitação de suporte foi enviada. Um agente entrará em contato em breve.")
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

# Inicia o bot (unchanged)
async def main():
    logger.info("Iniciando o bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())