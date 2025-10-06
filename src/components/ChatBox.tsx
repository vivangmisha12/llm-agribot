import React from "react";

interface ChatBoxProps {
  messages: { sender: string; text: string }[];
}

const ChatBox: React.FC<ChatBoxProps> = ({ messages }) => {
  return (
    <div className="chatbox">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`message ${msg.sender === "user" ? "user-msg" : "bot-msg"}`}
        >
          {msg.text}
        </div>
      ))}
    </div>
  );
};

export default ChatBox;
