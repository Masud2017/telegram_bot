from fastapi import FastAPI, Request
import requests
from dotenv import load_dotenv
import os
import uvicorn
from aiogram import Bot, Dispatcher, types
import json
from uuid import uuid4
from random import SystemRandom
import redis
import logging

load_dotenv(override=True)

bot = Bot(token=os.environ.get("TELEGRAM_BOT_TOKEN"))
app = FastAPI()

############################## Global Variables ###############################

users = {}
inventories = {}
boxes = {
    # "1": {
    #     "name": None,
    #     "image": None,
    #     "price": None,
    #     "probability": None
    # },
    # "2": {
    #     "name": None,
    #     "image": None,
    #     "price": None,
    #     "probability": None
    # },
    # "3": {
    #     "name": None,
    #     "image": None,
    #     "price": None,
    #     "probability": None
    # }
}
flow_control = None
box_state = None
flow_control_user = {}

# Parse the Redis URI
uri = "rediss://red-co58iiv79t8c739k9n3g:f8pIawA1WxZSqCL6UX6bBMyxdBQyypF7@oregon-redis.render.com:6379"

# Connect to Redis
redis_client = redis.from_url(uri)
# redis_client.set("key", "fooo")
print(redis_client.get("jhbdvcugvdc"))

###############################################################################

@app.get("/")
async def root():
    return {"message": "Hello World"}

async def transfer_currency(sender_id, receiver_id, amount):
    global users
    if amount < 0: return False
    if users[sender_id]["balance"] >= amount:
        users[sender_id]["balance"] -= amount
        users[receiver_id]["balance"] += amount
        # with open("/var/data/users.json", "w") as f:
        #     json.dump(users, f, indent=4)
        redis_client.set("users", json.dumps(users))
        return True
    return False

async def show_inventory(message: types.Message):
    global users
    inventory = {}
    for item in users[str(message.from_user.id)]["inventory"]:
        name = item["name"]
        if name in inventory:
            inventory[name] += 1
        else:
            inventory[name] = 1
    msg = "👜회원님의 보유아이템👜:\n"

    for i, item in enumerate(inventory):
        msg += f"{i+1}: {item} - 수량: {inventory[item]}\n"
    await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, reply_to_message_id=message.message_id, text=msg)
    return True

async def handle_admin_commands(message: types.Message):
    global flow_control, box_state
    if message.text.startswith("/addbalance"):
        try:
            _, user_id, amount = message.text.split()
            user_id = user_id
            amount = int(amount)
            if user_id in users:
                users[user_id]["balance"] += amount
            else:
                users[str(user_id)] = {
                    "first_name": "Unknown",
                    "last_name": "Unknown",
                    "username": "Unknown",
                    "balance": amount,
                    "inventory": []
                }
            # with open("/var/data/users.json", "w") as f:
            #     json.dump(users, f, indent=4)
            redis_client.set("users", json.dumps(users))
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"Successfully added {amount} to {user_id}")
        except:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please provide a valid user ID and amount in the following format:\n addbalance <user_id> <amount>")
    # elif message.text == "/setbox":
    #     global flow_control, box_state
    #     flow_control = "setbox"
    #     box_state = 1
    #     await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please enter box ID (1, 2, or 3)")
    elif message.text == "/addbox":
        flow_control = "addbox"
        box_state = 1
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="고유 ID를 입력하세요.")
    elif message.text == "/additem":
        flow_control = "additem"
        box_state = 1
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please enter box ID")
    elif message.text.startswith("/showitems"):
        try:
            _, box_id = message.text.split()
            box_id = box_id
            msg = f"Items in box {box_id}:\n"
            for i, item in enumerate(boxes[box_id]["items"]):
                msg += f"{i+1}: {item['name']} - Probability: {item['probability']}%\n"
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=msg)
        except:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please provide a valid box ID in the following format:\n /showitems <box_id>")
    elif message.text == "/unlistitem":
        flow_control = "unlistitem"
        box_state = 1
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please enter item name to unlist")
    elif message.text.startswith("/withdrawitem"):
        try:
            user_id = message.text.split()[1]
            item_name = message.text.split()[2]
            quantity = int(message.text.split()[3])
            for _ in range(quantity):
                for item in users[user_id]["inventory"]:
                    if item["name"] == item_name:
                        users[user_id]["inventory"].remove(item)
                        break
            # with open("/var/data/users.json", "w") as f:
            #     json.dump(users, f, indent=4)
            redis_client.set("users", json.dumps(users))
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"Successfully withdrawn {quantity} {item_name} from {user_id}")
        except:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please provide a valid user ID, item name, and quantity in the following format:\n /withdrawitem <user_id> <item_name> <quantity>")
    elif message.text.startswith("/editprobability"):
        try:
            _, box_id, item_name, probability = message.text.split()
            box_id = box_id
            item_name = item_name
            probability = int(probability)
            for item in boxes[box_id]["items"]:
                if item["name"] == item_name:
                    item["probability"] = probability
                    break
            # with open("/var/data/boxes.json", "w") as f:
            #     json.dump(boxes, f, indent=4)
            redis_client.set("boxes", json.dumps(boxes))
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"Successfully edited probability of {item_name} in box {box_id}")
        except:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please provide a valid box ID, item name, and probability in the following format:\n /editprobability <box_id> <item_name> <probability>")
    elif message.text == "/editbox":
        flow_control = "editbox"
        box_state = 1
        msg = "📦오픈 가능한 박스📦\n\n아이디 : 이름\n"
        for box_id in boxes:
            msg += f"{box_id}: {boxes[box_id]['name']}\n"
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=msg)
    elif message.text.startswith("/deletebox"):
        try:
            _, box_id = message.text.split()
            box_id = box_id
            if box_id in boxes:
                boxes.pop(box_id)
                # with open("/var/data/boxes.json", "w") as f:
                #     json.dump(boxes, f, indent=4)
                redis_client.set("boxes", json.dumps(boxes))
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"Successfully deleted box {box_id}")
            else:
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효하지 않은 박스 ID입니다.")
        except:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="Please provide a valid box ID in the following format:\n /deletebox <box_id>")
    elif message.text.startswith("/inventory"):
        try:
            _, user_id = message.text.split()
            user_id = user_id
            inventory = {}
            for item in users[user_id]["inventory"]:
                name = item["name"]
                if name in inventory:
                    inventory[name] += 1
                else:
                    inventory[name] = 1
            msg = f"{user_id}의 인벤토리:\n"
            for i, item in enumerate(inventory):
                msg += f"{i+1}: {item} - 수량: {inventory[item]}\n"
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=msg)
        except:
            await bot.send_message(
                reply_to_message_id=message.message_id,
                chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id,
                # text="Please provide a valid user ID in the following format:\n /inventory <user_id>" korean
                text="유효한 사용자 ID를 다음 형식으로 제공하십시오:\n /inventory <user_id>"
            )
    elif message.text.startswith("/showbalance"):
        try:
            _, user_id = message.text.split()
            user_id = user_id
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"{user_id}'s balance is {users[user_id]['balance']}")
        except:
            await bot.send_message(
                reply_to_message_id=message.message_id,
                chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id,
                # text="Please provide a valid user ID in the following format:\n /showbalance <user_id>" korean
                text="유효한 사용자 ID를 다음 형식으로 제공하십시오:\n /showbalance <user_id>"
            )

async def open_box(message: types.Message):
    global users, boxes, flow_control_user
    if len(boxes) == 0:
        await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, reply_to_message_id=message.message_id, text="📦오픈 가능한 박스가 없습니다📦")
        return
    flow_control_user[str(message.from_user.id)] = ("openbox", 1)
    msg = "📦오픈 가능한 박스📦\n\n"
    for i, box_id in enumerate(boxes):
        msg += f"{i+1}: {boxes[box_id]['name']} - {boxes[box_id]['price']} 포인트\n{boxes[box_id]['description']}\n\n"
    
    msg += "\n✅원하는 박스의 아이디를 적어주세요 !"
    await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, reply_to_message_id=message.message_id, text=msg)
    

async def handle_slash_commands(message: types.Message):
    if message.text == "/start" or message.text == "/help":
        msg = """
        안녕하세요! 각종 도움이 되는 도움말을 제공합니다!
/help - 명령어 도움말을 실행합니다.
/myid - 유저의 텔레그램 아이디를 제공 받을 수 있습니다.
/balance - 유저의 포인트 잔액을 확인할 수 있습니다.
/transfer <텔레그램 아이디> <금액> - 포인트를 회원에게 송금합니다.
/inventory - 유저의 인벤토리 현황을 볼 수 있습니다.
/openbox - 랜덤상자를 열 수 있습니다.
"""
        if message.from_user.id in [int(id) for id in os.environ.get("ADMIN_IDS").split(",")] and message.chat.type == "private":
            msg += """

어드민 명령어 
/addbalance <user_id> <amount> - Add balance to a user
/addbox - Add a new box
/showboxes - Show all available boxes
/additem - Add item to a box
/showitems <box_id> - Show all items in a box
/unlistitem <box_id> <item_name> - Unlist an item from a box
/withdrawitem <user_id> <item_name> <quantity> - Withdraw an item from a user's inventory
/editprobability <box_id> <item_name> <probability> - Edit probability of an item in a box
/editbox - Edit a box
/deletebox <box_id> - Delete a box"""
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=msg)
    elif message.text == "/myid":
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"회원님의 텔레그램 아이디는 {message.from_user.id} 입니다.")
    elif message.text == "/balance":
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"보유 잔액은 {users[str(message.from_user.id)]['balance']} 원입니다")
    elif message.text.startswith("/transfer"):
        try:
            _, receiver_id, amount = message.text.split()
            receiver_id = receiver_id
            amount = int(amount)
            if receiver_id in users:
                if await transfer_currency(str(message.from_user.id), receiver_id, amount):
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"{amount} 원이 성공적으로 {receiver_id} 으로 전송 되었습니다.")
                else:
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="잔액이 부족합니다.")
        except:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="양식에 맞게 수취인의 아이디와 금액을 기재해주세요. 예) /transfer <텔레그램 ID> <송금할 금액>")
    elif message.text == "/inventory":
        if len(users[str(message.from_user.id)]["inventory"]) == 0:
            await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="인벤토리가 비어있습니다.")
        else:
            await show_inventory(message)
    elif message.text == "/openbox":
        await open_box(message)
    elif message.text == "/showboxes":
        msg = "📦오픈 가능한 박스📦\n\n"
        for i, box_id in enumerate(boxes):
            msg += f"{i+1}: {boxes[box_id]['name']} - {boxes[box_id]['price']} 포인트\n{boxes[box_id]['description']}\n\n"
        await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=msg)
    elif message.from_user.id in [int(id) for id in os.environ.get("ADMIN_IDS").split(",")]:
        await handle_admin_commands(message)
    else:
        await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효하지 않은 명령어입니다.")

@app.post("/webhook")
async def webhook(request: Request):
    global flow_control, box_state
    data = await request.json()
    try: data["message"]["text"] = data["message"]["text"].replace("@groupmone_bot", "")
    except: pass
    message: types.Message = types.Message(**data["message"])

    if str(message.from_user.id) not in users:
        users[str(message.from_user.id)] = {
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "username": message.from_user.username,
            "balance": 0,
            "inventory": []
        }
        # with open("/var/data/users.json", "w") as f:
        #     json.dump(users, f, indent=4)
        redis_client.set("users", json.dumps(users))

    if message.text and message.text.startswith("/"):
        await handle_slash_commands(message)
    else:
        if flow_control and flow_control.startswith("addbox"):
            if box_state == 1:
                box_id = message.text
                if box_id in boxes:
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="해당 박스의 아이디는 이미 존재합니다. 다른 아이디를 입력해주세요.")
                    return
                box_state = 2
                flow_control = f"addbox:{box_id}"
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스 이름을 적어주세요.")
            elif box_state == 2:
                box_id = flow_control.split(":")[1]
                boxes[box_id] = {
                    "name": message.text,
                    "description": None,
                    "price": None,
                    "items": []
                }
                box_state = 3
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스 오픈 금액을 적어주세요.")
            elif box_state == 3:
                box_id = flow_control.split(":")[1]
                try: boxes[box_id]["price"] = int(message.text)
                except: 
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효한 가격을 적어주세요.")
                    return
                box_state = 4
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스에 대한 설명을 적어주세요.")
            elif box_state == 4:
                box_id = flow_control.split(":")[1]
                boxes[box_id]["description"] = message.text
                # with open("/var/data/boxes.json", "w") as f:
                #     json.dump(boxes, f, indent=4)
                redis_client.set("boxes", json.dumps(boxes))
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스 설정이 성공적으로 저장되었습니다.")
                flow_control = None

        elif flow_control and flow_control.startswith("additem"):
            if box_state == 1:
                box_id = message.text
                if box_id not in boxes:
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="의 박스 중 유효한 박스 번호를 적어주세요.")
                    return
                box_state = 2
                flow_control = f"additem:{box_id}"
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="아이템의 이름을 적어주세요.")
            elif box_state == 2:
                box_id = flow_control.split(":")[1]
                item_name = message.text
                box_state = 3
                flow_control = f"additem:{box_id}:{item_name}"
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="아이템의 확률을 적어주세요.")
            elif box_state == 3:
                box_id = flow_control.split(":")[1]
                item_name = flow_control.split(":")[2]
                boxes[box_id]["items"].append(
                    {
                        "name": item_name,
                        "probability": int(message.text if message.text else 50),
                    }
                )
                box_state = 4
                await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스 이미지를 보내주세요.")
            elif box_state == 4:
                box_id = flow_control.split(":")[1]
                item_name = flow_control.split(":")[2]
                if message.content_type == "photo":
                    destination = f"media/{uuid4()}.jpg"
                    file_id = message.photo[-1].file_id
                    boxes[box_id]["items"][-1]["image"] = file_id
                    # with open("/var/data/boxes.json", "w") as f:
                    #     json.dump(boxes, f, indent=4)
                    redis_client.set("boxes", json.dumps(boxes))
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="항목이 성공적으로 저장되었습니다.")
                else:
                    await bot.send_message(reply_to_message_id=message.message_id, chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효한 이미지를 보내주세요. ")
                    return
                flow_control = None
    
        elif str(message.from_user.id) in flow_control_user:
            if flow_control_user[str(message.from_user.id)][0] == "openbox":
                if flow_control_user[str(message.from_user.id)][1] == 1:
                    box_id = message.text
                    # Check if box_id is greater than length of boxes
                    if not box_id.isnumeric() or int(box_id) > len(boxes):
                        await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효하지 않은 박스 ID입니다.")
                        return
                    box_id = list(boxes.keys())[int(box_id)-1]
                    box = boxes[box_id]
                    if len(box["items"]) == 0:
                        await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="해당 아이템이 박스에 존재하지 않습니다.")
                        return
                    # Check if user has enough balance
                    if users[str(message.from_user.id)]["balance"] < box["price"]:
                        await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="잔액이 부족합니다.")
                        return
                    # Deduct balance
                    users[str(message.from_user.id)]["balance"] -= box["price"]
                    # Select a random item
                    random_item = SystemRandom().choices(population=box["items"], weights=[item["probability"] for item in box["items"]], k=1)[0]
                    # Add item to user's inventory
                    users[str(message.from_user.id)]["inventory"].append(random_item)
                    # with open("/var/data/users.json", "w") as f:
                    #     json.dump(users, f, indent=4)
                    redis_client.set("users", json.dumps(users))
                    await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"🎇 축하드립니다 !! 상자에서 {random_item['name']}이 나왔습니다 🎇")
                    # Send image of the item
                    await bot.send_photo(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, photo=random_item["image"], caption=random_item["name"])
                    flow_control_user.pop(str(message.from_user.id))
    
        elif flow_control and flow_control.startswith("unlistitem"):
            if box_state == 1:
                box_state = 2
                msg = ""
                for i, box_id in enumerate(boxes):
                    msg += f"{i+1}: {boxes[box_id]['name']}\n"
                msg += "\n박스를 선택하기 위해 박스의 아이디를 적어주세요, 전체의 경우 \"all\"을 적어주세요."
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=msg)
                flow_control = f"unlistitem:{message.text}"
            elif box_state == 2:
                if message.text == "all":
                    flow_control += ":all"
                else:
                    if not message.text.isnumeric() or int(message.text) > len(boxes):
                        await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효하지 않은 박스 ID입니다.")
                        return
                    box_id = list(boxes.keys())[int(message.text)-1]
                    flow_control += f":{box_id}"
                box_state = 3
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유저의 인벤토리에서 아이템을 제거할 수량을 적어주세요.")
            elif box_state == 3:
                if not message.text.isnumeric():
                    await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효한 숫자를 입력해주세요.")
                    return
                item_name = flow_control.split(":")[1]
                box_id = flow_control.split(":")[2]
                count = int(message.text)
                if count > 500: count = 500
                if count < 0: count = 0
                if box_id == "all":
                    for box_id in boxes:
                        boxes[box_id]["items"] = [item for item in boxes[box_id]["items"] if item["name"] != item_name]
                else:
                    boxes[box_id]["items"] = [item for item in boxes[box_id]["items"] if item["name"] != item_name]
                for _ in range(count):
                    for user in users:
                        for item in users[user]["inventory"]:
                            if item["name"] == item_name:
                                users[user]["inventory"].remove(item)
                                break
                # with open("/var/data/users.json", "w") as f:
                #     json.dump(users, f, indent=4)
                redis_client.set("users", json.dumps(users))
                # with open("/var/data/boxes.json", "w") as f:
                #     json.dump(boxes, f, indent=4)
                redis_client.set("boxes", json.dumps(boxes))
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text=f"성공적으로 {count} {item_name}이 유저의 인벤토리에서 제거 되었습니다.")
                flow_control = None
                
        elif flow_control and flow_control.startswith("editbox"):
            if box_state == 1:
                box_state = 2
                box_id = message.text
                if box_id not in boxes:
                    await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효하지 않은 박스 ID입니다.")
                    return
                flow_control = f"editbox:{box_id}"
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스 이름을 적어주세요.")
            elif box_state == 2:
                box_id = flow_control.split(":")[1]
                box_name = message.text
                boxes[box_id]["name"] = box_name
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스 오픈 금액을 적어주세요.")
                box_state = 3
            elif box_state == 3:
                box_id = flow_control.split(":")[1]
                try:
                    box_price = int(message.text)
                    boxes[box_id]["price"] = box_price
                except:
                    await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="유효한 가격을 적어주세요.")
                    return
                box_state = 4
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="박스에 대한 설명을 적어주세요.")
            elif box_state == 4:
                box_id = flow_control.split(":")[1]
                box_description = message.text
                boxes[box_id]["description"] = box_description
                # with open("/var/data/boxes.json", "w") as f:
                #     json.dump(boxes, f, indent=4)
                redis_client.set("boxes", json.dumps(boxes))
                await bot.send_message(chat_id=message.from_user.id if message.chat.type == "private" else message.chat.id, text="성공적으로 박스를 수정했습니다.")
                flow_control = None
    return {"status": "ok"}

def setWebhook(bot_token, webhook_url, secret_token):
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}&drop_pending_updates=true&max_connections=100&secret_token={secret_token}"
    response = requests.get(url)
    return response.json()

def getWebhookInfo(bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    response = requests.get(url)
    return response.json()

# def setup():
#     global users, inventories, boxes
    # if os.path.isfile("/var/data/users.json"):
    #     with open("/var/data/users.json", "r") as f:
    #         users = json.load(f)
    # else:
    #     with open("/var/data/users.json", "w") as f:
    #         json.dump(users, f, indent=4)
    # if os.path.isfile("/var/data/inventories.json"):
    #     with open("/var/data/inventories.json", "r") as f:
    #         inventories = json.load(f)
    # else:
    #     with open("/var/data/inventories.json", "w") as f:
    #         json.dump(inventories, f, indent=4)
    # if os.path.isfile("/var/data/boxes.json"):
    #     with open("/var/data/boxes.json", "r") as f:
    #         boxes = json.load(f)
    # else:
    #     with open("/var/data/boxes.json", "w") as f:
    #         json.dump(boxes, f, indent=4)

users_str = redis_client.get("users")
if not users_str:
    redis_client.set("users", json.dumps(users))
else:
    users = json.loads(users_str.decode("utf-8"))

inventories_str = redis_client.get("inventories")
if not inventories_str:
    redis_client.set("inventories", json.dumps(inventories))
else:
    inventories = json.loads(inventories_str.decode("utf-8"))

boxes_str = redis_client.get("boxes")
if not boxes_str:
    redis_client.set("boxes", json.dumps(boxes))
else:
    boxes = json.loads(boxes_str.decode("utf-8"))
    logging.info(boxes)

# if __name__ == '__main__':
#     # setup()
#     setWebhook(
#         bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
#         webhook_url=os.environ.get("SERVER_ADDRESS") + "/webhook",
#         secret_token=os.environ.get("TELEGRAM_BOT_SECRET_TOKEN")
#     )
#     print(getWebhookInfo(os.environ.get("TELEGRAM_BOT_TOKEN")))

#     uvicorn.run(app, host="0.0.0.0", port=8000)