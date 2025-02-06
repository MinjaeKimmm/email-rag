from pathlib import Path
import datetime
import json
import re
import win32com.client
from collections import defaultdict

def get_email_time(message):
    try:
        return message.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S")
    except:
        try:
            return message.CreationTime.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return "Unknown Time"

def create_safe_folder_name(topic, timestamp, max_topic_length=100):
    clean_topic = re.sub(r'[^0-9a-zA-Z]+', '_', topic)
    clean_topic = clean_topic[:max_topic_length]
    return f"{clean_topic}_{timestamp}"

def backup_emails():
   # Setup directories
   base_dir = Path.cwd() / "data"
   emails_dir = base_dir / "emails"
   base_dir.mkdir(parents=True, exist_ok=True)
   emails_dir.mkdir(parents=True, exist_ok=True)

   # Connect to Outlook
   outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
   inbox = outlook.GetDefaultFolder(6)
   
   # Group by conversations first
   conversations = defaultdict(list)
   messages = inbox.Items

   # First pass: group messages by conversation
   for message in messages:
       try:
           conv_id = message.ConversationID
           conversations[conv_id].append({
               "Message": message,
               "Metadata": {
                    "Subject": message.Subject or "No Subject",
                    "SenderName": getattr(message, "SenderName", "Unknown Sender"),
                    "SenderEmail": getattr(message, "SenderEmailAddress", ""),
                    "To": getattr(message, "To", ""),
                    "CC": getattr(message, "CC", ""),
                    "ReceivedTime": get_email_time(message),
                    "ConversationTopic": message.ConversationTopic,
                    "HasAttachments": message.Attachments.Count > 0
                }
           })
       except Exception as e:
           print(f"Error grouping email: {e}")

   # Process each conversation
   email_data = []
   for conv_id, messages in conversations.items():
       try:
           # Create conversation folder using first message's topic
           first_msg = messages[0]["Metadata"]
           timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
           folder_name = create_safe_folder_name(first_msg["ConversationTopic"], timestamp)
           conv_folder = emails_dir / folder_name
           conv_folder.mkdir(parents=True, exist_ok=True)

           # Process each message in conversation
           conversation_data = {
               "ConversationID": conv_id,
               "Topic": first_msg["ConversationTopic"],
               "Messages": []
           }

           for idx, msg_data in enumerate(sorted(messages, key=lambda x: x["Metadata"]["ReceivedTime"])):
               message = msg_data["Message"]
               metadata = msg_data["Metadata"]

               # Create message folder within conversation
               msg_folder = conv_folder / f"message_{idx+1}"
               msg_folder.mkdir(parents=True, exist_ok=True)

               # Save body
               body_file = msg_folder / "EMAIL_BODY.txt"
               body_file.write_text(message.Body or "", encoding="utf-8")

               # Save attachments
               attachment_files = []
               for attachment in message.Attachments:
                   clean_filename = re.sub(r'[^0-9a-zA-Z.]+', '_', attachment.FileName)
                   attachment_path = msg_folder / clean_filename
                   attachment.SaveAsFile(str(attachment_path))
                   attachment_files.append(clean_filename)

               # Add message data with new metadata
               message_data = {
                    "Subject": metadata["Subject"],
                    "SenderName": metadata["SenderName"],
                    "SenderEmail": metadata["SenderEmail"],
                    "To": metadata["To"],
                    "CC": metadata["CC"],
                    "ReceivedTime": metadata["ReceivedTime"],
                    "ConversationTopic": metadata["ConversationTopic"],
                    "Body": message.Body or "",  
                    "AttachmentFiles": [  
                        str((msg_folder / clean_filename).relative_to(base_dir))
                        for clean_filename in attachment_files
                    ],
                    "OrderInConversation": idx + 1
                }
               conversation_data["Messages"].append(message_data)

           email_data.append(conversation_data)
           print(f"Processed conversation: {first_msg['ConversationTopic']}")

       except Exception as e:
           print(f"Error processing conversation {conv_id}: {e}")

   # Save JSON with conversation structure
   json_file = base_dir / "email_conversations.json"
   with json_file.open("w", encoding="utf-8") as f:
       json.dump(email_data, f, indent=4, ensure_ascii=False)

   print(f"Backup complete. Emails saved to {emails_dir}")

if __name__ == "__main__":
   backup_emails()