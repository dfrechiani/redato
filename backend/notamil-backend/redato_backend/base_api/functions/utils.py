import random
import string


def generate_password():
    uppercase_letter = random.choice(string.ascii_uppercase)
    lowercase_letter = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special_char = random.choice(string.punctuation)

    # Generate the remaining characters
    remaining_length = 8  # Minimum password length
    remaining_chars = "".join(
        random.choices(
            string.ascii_letters + string.digits + string.punctuation,
            k=remaining_length - 4,  # -4 for the four required characters
        )
    )

    # Combine all parts and shuffle
    all_chars = (
        uppercase_letter + lowercase_letter + digit + special_char + remaining_chars
    )
    char_list = list(all_chars)
    random.shuffle(char_list)
    return "".join(char_list)
