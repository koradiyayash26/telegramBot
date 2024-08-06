from django.core.management.base import BaseCommand
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import httpx
from asgiref.sync import sync_to_async
from myapp.models import Purchase  # Adjust the import based on your app name
from decimal import Decimal
import datetime
import asyncio

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Define conversation states
ID, VS_TOKEN, SELECT_PURCHASE = range(3)

# Replace with your bot's token
BOT_TOKEN = '7026601318:AAFLb8ySkLt2_tkgNWBrZ0p1LAVp-ZGlWcM'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler."""
    await update.message.reply_text('Hello! Use /price to get the price of a token. Please provide the token ID when prompted.')

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /price command."""
    await update.message.reply_text('Please enter the token ID:')
    return ID

async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle token ID input."""
    token_id = update.message.text.strip()
    await update.message.reply_text(f'Please enter the vsToken for {token_id}:')
    context.user_data['token_id'] = token_id
    return VS_TOKEN

async def handle_vs_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle vsToken input and fetch price."""
    vs_token = update.message.text.strip()
    token_id = context.user_data.get('token_id', '')

    url = f'https://price.jup.ag/v6/price?ids={token_id}&vsToken={vs_token}'
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            data = response.json()

            logger.info(f"API Response: {data}")

            if 'data' in data and token_id in data['data']:
                price = data['data'][token_id]['price']
                vsTokenSymbol = data['data'][token_id]['vsTokenSymbol']
                formatted_price = f"${price:,.2f}"

                # Create buttons
                keyboard = [
                    [InlineKeyboardButton("Buy", callback_data='buy')],
                    [InlineKeyboardButton("Sell", callback_data='sell')],
                    [InlineKeyboardButton("Position", callback_data='position')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    f"Token ID: {token_id}\n"
                    f"Based on: {vsTokenSymbol}\n"
                    f"Price: {formatted_price}",
                    reply_markup=reply_markup
                )
                context.user_data['vs_token'] = vs_token
                context.user_data['vsTokenSymbol'] = vsTokenSymbol
                context.user_data['formatted_price'] = formatted_price
                context.user_data['swap_value'] = '0.5'
            else:
                await update.message.reply_text("Invalid token ID or vsToken, or price not available. Please try again.")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            await update.message.reply_text("Failed to retrieve the price. Please try again later.")
    
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline buttons."""
    query = update.callback_query

    if query is None:
        logger.error("Received an update without callback_query.")
        return

    await query.answer()
    choice = query.data
    token_id = context.user_data.get('token_id', '')
    vs_token = context.user_data.get('vs_token', '')
    vsTokenSymbol = context.user_data.get('vsTokenSymbol', '')
    formatted_price = context.user_data.get('formatted_price', '')
    swap_value = context.user_data.get('swap_value', '0.5')  # Default to 0.5 if not set

    try:
        if choice == 'buy':
            # Show swap options with default (0.5) pre-selected
            keyboard = [
                [InlineKeyboardButton("✅ Swap 0.5", callback_data='swap_0.5') if swap_value == '0.5' else InlineKeyboardButton("Swap 0.5", callback_data='swap_0.5')],
                [InlineKeyboardButton("✅ Swap 1", callback_data='swap_1') if swap_value == '1' else InlineKeyboardButton("Swap 1", callback_data='swap_1')],
                [InlineKeyboardButton("Confirm Buy", callback_data='confirm_buy')],
                [InlineKeyboardButton("Back", callback_data='back_to_options')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"Token ID: {token_id}\n"
                     f"Based on: {vsTokenSymbol}\n"
                     f"Price: {formatted_price}\n"
                     f"Swap option: {swap_value} {vsTokenSymbol}\n"
                     f"Confirm your buy:",
                reply_markup=reply_markup
            )
        elif choice == 'sell':
            context.user_data['waiting_for_sell_vs_token'] = True
            keyboard = [
                [InlineKeyboardButton("Back", callback_data='back_to_options')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"Please enter the vsToken for selling tokens:",
                reply_markup=reply_markup
            )
        elif choice == 'position':
            await asyncio.sleep(0.5)
            
            purchases = await sync_to_async(list)(Purchase.objects.filter(token_id=token_id, vsTokenSymbol=vsTokenSymbol, open=True))  # Wrap with sync_to_async

            if purchases:
                # Fetch current price
                url = f'https://price.jup.ag/v6/price?ids={token_id}&vsToken={vs_token}'
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.get(url)
                        data = response.json()
                        
                        logger.info(f"API Response: {data}")
                        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        if 'data' in data and token_id in data['data']:
                            current_price = Decimal(data['data'][token_id]['price'])  # Ensure current_price is Decimal
                            formatted_current_price = f"${current_price:,.2f}"
                            table_text = f"Current Price: {formatted_current_price}\nCurrent Time: {current_time} \n\n\n"
                            table_text += f"{'ID':<5} {'Token':<15} {'Buy Price':<15} {'Buys':<15} {'Profit':<15}\n"
                            table_text += "-" * 80 + "\n"

                            for purchase in purchases:
                                buy_price = Decimal(purchase.buy_price)  # Ensure buy_price is Decimal
                                profit = current_price - buy_price
                                formatted_profit = f"${profit:,.2f}"

                                table_text += (
                                    f"{purchase.id:<5} "
                                    f"{purchase.token_id:<15} "
                                    f"${buy_price:,.2f}     "
                                    f"{' ' * 5} {purchase.swap_value:<15} "
                                    f"{formatted_profit}\n"
                                )
                            
                            # Add a refresh and back button
                            keyboard = [
                                [InlineKeyboardButton("Refresh", callback_data='position')],
                                [InlineKeyboardButton("Back", callback_data='back_to_options')]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await query.edit_message_text(
                                text=table_text,
                                reply_markup=reply_markup
                            )
                        else:
                            await query.edit_message_text("Failed to retrieve the latest price.")
                    except httpx.RequestError as e:
                        logger.error(f"Request error: {e}")
                        await query.edit_message_text("Failed to retrieve the price. Please try again later.")
            else:
                keyboard = [
                    [InlineKeyboardButton("Buy", callback_data='buy')],
                    [InlineKeyboardButton("Sell", callback_data='sell')],
                    [InlineKeyboardButton("Position", callback_data='position')]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text="No open purchases found for this token.",
                    reply_markup=reply_markup
                )
                
        elif choice.startswith('swap_'):
            swap_value = choice.split('_')[1]
            context.user_data['swap_value'] = swap_value

            # Create the buttons with the tick mark on the selected swap option
            keyboard = [
                [InlineKeyboardButton("✅ Swap 0.5", callback_data='swap_0.5') if swap_value == '0.5' else InlineKeyboardButton("Swap 0.5", callback_data='swap_0.5')],
                [InlineKeyboardButton("✅ Swap 1", callback_data='swap_1') if swap_value == '1' else InlineKeyboardButton("Swap 1", callback_data='swap_1')],
                [InlineKeyboardButton("Confirm Buy", callback_data='confirm_buy')],
                [InlineKeyboardButton("Back", callback_data='back_to_options')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"Token ID: {token_id}\n"
                     f"Based on: {vsTokenSymbol}\n"
                     f"Price: {formatted_price}\n"
                     f"Swap option: {swap_value} {vsTokenSymbol}\n"
                     f"Confirm your buy:",
                reply_markup=reply_markup
            )
        elif choice == 'confirm_buy':
            swap_value = context.user_data.get('swap_value', '0.5')  # Default to 0.5 if not set
            
            # Save the purchase data to the database
            purchase = await sync_to_async(Purchase.objects.create)(
                # user=None,  # Update with the actual user if available
                token_id=token_id,
                vs_token=vs_token,
                vsTokenSymbol=vsTokenSymbol,
                buy_price=float(formatted_price.replace('$', '').replace(',', '')),
                swap_value=float(swap_value)
            )
            keyboard = [
                [InlineKeyboardButton("Back", callback_data='back_to_options')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # Notify user about the purchase with purchase ID
            await query.edit_message_text(
                text=f"You have bought {swap_value} {vsTokenSymbol} of token {token_id}.\n"
                     f"Purchase ID: {purchase.id}",
                reply_markup=reply_markup  # Hide the buttons
            )

            # Log to confirm the action
            logger.info(f"User confirmed buy: {swap_value} {vs_token} of token {token_id} with Purchase ID {purchase.id}")

            # Optionally clear user data if necessary
            context.user_data['token_id'] = token_id
            context.user_data['vs_token'] = vs_token
            context.user_data['formatted_price'] = formatted_price
            
            # Optional: Log state of context user data for debugging
            logger.info(f"User data after buy confirmation: {context.user_data}")

        elif choice.startswith('select_'):
            # User selected a purchase to sell
            purchase_id = choice.split('_')[1]
            context.user_data['selected_purchase_id'] = purchase_id
            context.user_data['waiting_for_sell_price'] = True
            
            # Fetch the selected purchase
            purchase = await sync_to_async(Purchase.objects.get)(id=purchase_id)
            token_id = purchase.token_id
            
            # Fetch latest price from URL
            url = f'https://price.jup.ag/v6/price?ids={token_id}&vsToken={vs_token}'
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url)
                    data = response.json()

                    if 'data' in data and token_id in data['data']:
                        current_price = Decimal(data['data'][token_id]['price'])
                        formatted_current_price = f"${current_price:,.2f}"
                        
                        keyboard = [[InlineKeyboardButton("Confirm Sell", callback_data='confirm_sell')],
                                    [InlineKeyboardButton("Back", callback_data='back_to_options')]]
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(
                            text=f"Selected Purchase ID: {purchase_id}\n"
                                 f"Current Price: {formatted_current_price}\n"
                                 f"Confirm Sell with this price?",
                                 reply_markup=reply_markup
                        )
                        
                        context.user_data['sell_price'] = current_price
    
                    else:
                        await query.edit_message_text("Failed to retrieve the latest price.")
                except httpx.RequestError as e:
                    logger.error(f"Request error: {e}")
                    await query.edit_message_text("Failed to retrieve the price. Please try again later.")
                    
        elif choice == 'confirm_sell':
            
            purchase_id = context.user_data.get('selected_purchase_id')
            
            if purchase_id:
                # Fetch the purchase again and update it with sell details
                purchase = await sync_to_async(Purchase.objects.get)(id=purchase_id)
                sell_price = context.user_data.get('sell_price')

                if purchase and sell_price:
                    purchase.sell_price = sell_price
                    purchase.open = False
                    
                    await sync_to_async(purchase.save)()
                    
                    keyboard = [
                        [InlineKeyboardButton("Back", callback_data='back_to_options')]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        text=f"Token Sold Successfully\n"
                             f"Token {purchase.token_id}\n"
                             f"Based {purchase.vsTokenSymbol}\n"
                             f"Buy Price: ${purchase.buy_price}\n"
                             f"Sell Price: ${sell_price:,.2f}\n"
                             f"Purchase ID: {purchase_id}",
                        reply_markup=reply_markup
                    )
                else:
                    await query.edit_message_text("An error occurred while processing the sale. Please try again.")
            else:
                await query.edit_message_text("No purchase selected for selling.")

        elif choice == 'back_to_options':
            keyboard = [
                [InlineKeyboardButton("Buy", callback_data='buy')],
                [InlineKeyboardButton("Sell", callback_data='sell')],
                [InlineKeyboardButton("Position", callback_data='position')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"Token ID: {token_id}\n"
                     f"Based on: {vsTokenSymbol}\n"
                     f"Price: {formatted_price}",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        await query.edit_message_text("An error occurred. Please try again later.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user text messages."""
    user_input = update.message.text.strip()

    if context.user_data.get('waiting_for_sell_vs_token'):
        # Handle vs_token input for selling
        context.user_data['vs_token'] = user_input
        context.user_data['waiting_for_sell_vs_token'] = False
        
        # Fetch open purchases with the provided vs_token
        purchases = await sync_to_async(list)(Purchase.objects.filter(vs_token=user_input, open=True))
        
        if purchases:
            keyboard = [[InlineKeyboardButton(f"Token: {purchase.token_id} \nBased: {purchase.vsTokenSymbol} \nBuy Price: ${purchase.buy_price} \nBuys: {purchase.swap_value}", callback_data=f'select_{purchase.id}')] for purchase in purchases]
            keyboard.append([InlineKeyboardButton("Back", callback_data='back_to_options')])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                text="Please select the purchase you want to sell:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("No open purchases found with that vsToken.")
            
    elif user_input.replace('.', '', 1).isdigit():
        # Handle user input as a sell price if we're in the 'sell' state
        if context.user_data.get('waiting_for_sell_price'):
            token_id = context.user_data.get('token_id', '')
            formatted_sell_price = context.user_data.get('formatted_price', '')
            await update.message.reply_text(f"Processing sell price: {user_input}")

            # Call the function to update sell price
            price = float(user_input.replace('$', '').replace(',', ''))
            purchase = await sync_to_async(Purchase.objects.get)(
                id=price, token_id=token_id, open=True
            )
            
            purchase.sell_price = Decimal(formatted_sell_price.replace('$', '').replace(',', ''))
            purchase.open = False
            
            await sync_to_async(purchase.save)()
            keyboard = [
                [InlineKeyboardButton("Back", callback_data='back_to_options')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Clear the waiting state
            context.user_data['waiting_for_sell_price'] = False
            await update.message.reply_text(f"Token Sold Successfully \n Token {token_id} \n Buy Price ${purchase.buy_price} \n and sell Price ${purchase.sell_price} \n Sell Id {price}",
                                      reply_markup=reply_markup)
        else:
            # Handle other user inputs
            await update.message.reply_text(f'You entered {user_input}')
    else:
        await update.message.reply_text('Please enter a valid number.')

class Command(BaseCommand):
    help = 'Run the Telegram bot'

    def handle(self, *args, **options):
        application = Application.builder().token(BOT_TOKEN).build()

        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler('price', price_command)],
            states={
                ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_id)],
                VS_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vs_token)],
            },
            fallbacks=[],
        )

        application.add_handler(CommandHandler('start', start))
        application.add_handler(conversation_handler)
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        application.run_polling()
