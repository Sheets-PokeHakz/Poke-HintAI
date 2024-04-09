import requests
from PIL import Image
from io import BytesIO

# URL of your image identification API
api_url = 'http://192.168.0.104:5000/identify'

# URL of the image you want to identify
image_url = 'https://media.discordapp.net/attachments/1099716491705851984/1223319455279485110/pokemon.jpg?ex=66196c06&is=6606f706&hm=50c14756f1727e6e196e3628d188d659ea0405c10210fbd9819f6bd9bc03f7ad&=&format=webp&width=600&height=375'

# Fetch the image from the URL
response = requests.get(image_url)

if response.status_code == 200:
    # Read the image content
    image_data = response.content

    # Prepare the request payload with the image data
    payload = {'image': image_data}

    # Send the POST request to the API
    response = requests.post(api_url, files=payload)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        pokemon_name = data['pokemon_name']
        confidence = data['confidence']
        print(f"The identified Pokemon is {pokemon_name} with confidence {confidence}%")
    else:
        print(f"Error: {response.status_code} - {response.text}")
else:
    print(f"Failed to fetch the image: {response.status_code}")
