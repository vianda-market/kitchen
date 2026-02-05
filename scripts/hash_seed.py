from passlib.context import CryptContext

# Configure the password context. Adjust schemes if necessary.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_hash(password: str) -> str:
    return pwd_context.hash(password)

if __name__ == "__main__":
    # Replace these with the actual plain text passwords for admin and bot_chef
    admin_plain = "admin_password"  # Replace with the admin password in plain text
    bot_chef_plain = "bot_chef_password"  # Replace with the bot_chef password in plain text

    admin_hashed = generate_hash(admin_plain)
    bot_chef_hashed = generate_hash(bot_chef_plain)

    print("Admin hashed password:")
    print(admin_hashed)
    print("\nBot Chef hashed password:")
    print(bot_chef_hashed)
