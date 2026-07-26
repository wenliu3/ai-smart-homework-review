export interface RenderedAssistantMessage {
  role: "user" | "assistant";
  content: string;
  html: string;
}
