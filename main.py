
import os
import json
import requests
from pyrogram import Client, filters
from pyrogram.types import Message

# API base URL
api = 'https://api.classplusapp.com/v2'

# Initialize the bot with your API credentials
api_id = '27862677'
api_hash = 'e343ce2c81b2b6c2c0d6bee58284e3bd'
bot_token = '6891484332:AAHAiVZDQZc7CHW8SRYg_iVe-rC3e20_E2w'

bot = Client(
    "my_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

# Function to create HTML file
def create_html_file(file_name, batch_name, contents):
    tbody = ''
    parts = contents.split('\n')
    for part in parts:
        split_part = [item.strip() for item in part.split(':', 1)]
    
        text = split_part[0] if split_part[0] else 'Untitled'
        url = split_part[1].strip() if len(split_part) > 1 and split_part[1].strip() else 'No URL'

        tbody += f'<tr><td>{text}</td><td><a href="{url}" target="_blank">{url}</a></td></tr>'

    with open('cptxtextract/template.html', 'r') as fp:
        file_content = fp.read()
    title = batch_name.strip()
    with open(file_name, 'w') as fp:
        fp.write(file_content.replace('{{tbody_content}}', tbody).replace('{{batch_name}}', title))


# Function to fetch course content recursively
def get_course_content(session, course_id, folder_id=0):
    fetched_contents = ""

    params = {
        'courseId': course_id,
        'folderId': folder_id,
    }

    res = session.get(f'{api}/course/content/get', params=params)

    if res.status_code == 200:
        res_json = res.json()

        contents = res_json.get('data', {}).get('courseContent', [])

        for content in contents:
            if content['contentType'] == 1:
                resources = content.get('resources', {})

                if resources.get('videos') or resources.get('files'):
                    sub_contents = get_course_content(session, course_id, content['id'])
                    fetched_contents += sub_contents

            elif content['contentType'] == 2:
                name = content.get('name', '')
                id = content.get('contentHashId', '')

                headers = {
                    "Host": "api.classplusapp.com",
                    # Add more headers if needed
                }

                params = {
                    'contentId': id
                }

                r = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params)
                url = r.json().get('url')

                if url:
                    content = f'{name}:{url}\n'
                    fetched_contents += content

            else:
                name = content.get('name', '')
                url = content.get('url', '')
                content = f'{name}:{url}\n'
                fetched_contents += content

    return fetched_contents


# Command handlers
@bot.on_message(filters.command(["start"]))
async def start_command(bot, message):
    await message.reply_text("Hi, I am **Classplus txt Downloader**.\n\nPress **/classplus** to continue.")


@bot.on_message(filters.command(["classplus"]))
async def classplus_command(bot, message):
    try:
        input_text = await bot.ask(message.chat.id, text="SEND YOUR CREDENTIALS AS SHOWN BELOW\n\nORGANISATION CODE:\n\nPHONE NUMBER:\n\nOR SEND\nACCESS TOKEN:")

        creds = input_text.text.strip()
        session = requests.Session()

        # Headers
        headers = {
            # Add necessary headers
        }

        logged_in = False

        if '\n' in creds:
            org_code, phone_no = [cred.strip() for cred in creds.split('\n')]

            if org_code.isalpha() and phone_no.isdigit() and len(phone_no) == 10:
                res = session.get(f'{api}/orgs/{org_code}')

                if res.status_code == 200:
                    res_json = res.json()
                    org_id = int(res_json['data']['orgId'])

                    data = {
                        'countryExt': '91',
                        'mobile': phone_no,
                        'orgCode': org_code,
                        'orgId': org_id,
                        'viaSms': 1,
                    }

                    res = session.post(f'{api}/otp/generate', data=json.dumps(data))

                    if res.status_code == 200:
                        res_json = res.json()
                        session_id = res_json['data']['sessionId']

                        user_otp = await bot.ask(message.chat.id, text="Send your OTP: ")

                        if user_otp.text.isdigit():
                            otp = user_otp.text.strip()

                            data = {
                                "otp": otp,
                                "countryExt": "91",
                                "sessionId": session_id,
                                "orgId": org_id,
                                "fingerprintId": "",
                                "mobile": phone_no
                            }

                            res = session.post(f'{api}/users/verify', data=json.dumps(data))
                            res_json = res.json()

                            if res_json['status'] == 'success':
                                user_id = res_json['data']['user']['id']
                                token = res_json['data']['token']
                                session.headers['x-access-token'] = token
                                logged_in = True
                                await message.reply_text(f"Your access token for future uses -\n\n{token}")

                            else:
                                raise Exception('Failed to verify OTP.')

                        else:
                            raise Exception('Invalid OTP format.')

                    else:
                        raise Exception('Failed to generate OTP.')

                else:
                    raise Exception('Failed to get organization details.')

            else:
                raise Exception('Invalid organization code or phone number format.')

        else:
            token = creds
            session.headers['x-access-token'] = token

            res = session.get(f'{api}/users/details')

            if res.status_code == 200:
                res_json = res.json()
                user_id = res_json['data']['responseData']['user']['id']
                logged_in = True

            else:
                raise Exception('Failed to get user details.')

        if logged_in:
            params = {
                'userId': user_id,
                'tabCategoryId': 3
            }

            res = session.get(f'{api}/profiles/users/data', params=params)

            if res.status_code == 200:
                res_json = res.json()
                courses = res_json['data']['responseData']['coursesData']

                if courses:
                    text = ''

                    for cnt, course in enumerate(courses, start=1):
                        name = course['name']
                        text += f'{cnt}. {name}\n'

                    selected_course_num = await bot.ask(message.chat.id, text=f"Send the index number of the course to download:\n\n{text}")

                    if selected_course_num.text.isdigit() and 1 <= int(selected_course_num.text) <= len(courses):
                        selected_course_index = int(selected_course_num.text.strip())
                        selected_course_id = courses[selected_course_index - 1]['id']
                        selected_course_name = courses[selected_course_index - 1]['name']

                        msg = await bot.send_message(message.chat.id, text="Now extracting your course content...")

                        course_content = get_course_content(session, selected_course_id)

                        if course_content:
                            text_file = f"Classplus_{selected_course_name}.txt"
                            html_file = f"Classplus_{selected_course_name}.html"

                            with open(text_file, 'w') as f:
                                f.write(course_content)

                            create_html_file(html_file, selected_course_name, course_content)

                            await bot.send_document(message.chat.id, document=text_file, caption=f"App Name: Classplus\nBatch Name: {selected_course_name}")
                            await bot.send_document(message.chat.id, document=html_file, caption=f"App Name: Classplus\nBatch Name: {selected_course_name}")

                            os.remove(text_file)
                            os.remove(html_file)

                        else:
                            raise Exception('No content found in the selected course.')

                    else:
                        raise Exception('Invalid course index provided.')

                else:
                    raise Exception('No courses found for the user.')

            else:
                raise Exception('Failed to fetch user courses.')

    except Exception as e:
        print(f"Error: {e}")

# Start the bot
bot.run()
