export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      conversations: {
        Row: {
          character_id: string
          created_at: string
          id: string
          title: string
          updated_at: string
          user_id: string
        }
        Insert: {
          character_id: string
          created_at?: string
          id?: string
          title?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          character_id?: string
          created_at?: string
          id?: string
          title?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      entities: {
        Row: {
          aliases: string[] | null
          character_id: string
          created_at: string
          id: string
          last_mentioned_at: string
          mention_count: number
          name: string
          name_normalized: string
          notes: string | null
          type: string
          user_id: string
        }
        Insert: {
          aliases?: string[] | null
          character_id?: string
          created_at?: string
          id?: string
          last_mentioned_at?: string
          mention_count?: number
          name: string
          name_normalized: string
          notes?: string | null
          type?: string
          user_id: string
        }
        Update: {
          aliases?: string[] | null
          character_id?: string
          created_at?: string
          id?: string
          last_mentioned_at?: string
          mention_count?: number
          name?: string
          name_normalized?: string
          notes?: string | null
          type?: string
          user_id?: string
        }
        Relationships: []
      }
      entity_relations: {
        Row: {
          created_at: string
          from_entity: string
          id: string
          label: string
          strength: number
          to_entity: string
          user_id: string
        }
        Insert: {
          created_at?: string
          from_entity: string
          id?: string
          label: string
          strength?: number
          to_entity: string
          user_id: string
        }
        Update: {
          created_at?: string
          from_entity?: string
          id?: string
          label?: string
          strength?: number
          to_entity?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "entity_relations_from_entity_fkey"
            columns: ["from_entity"]
            isOneToOne: false
            referencedRelation: "entities"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "entity_relations_to_entity_fkey"
            columns: ["to_entity"]
            isOneToOne: false
            referencedRelation: "entities"
            referencedColumns: ["id"]
          },
        ]
      }
      furina_ai_preferences: {
        Row: {
          chat_provider: string
          use_nvidia_chat: boolean
          embedding_issue: string | null
          background_text_issue: string | null
          use_nvidia: boolean
          use_openrouter: boolean
          lovable_background: boolean
          lovable_chat: boolean
          use_gemini: boolean
          user_id: string
        }
        Insert: {
          chat_provider?: string
          use_nvidia_chat?: boolean
          embedding_issue?: string | null
          background_text_issue?: string | null
          use_nvidia?: boolean
          use_openrouter?: boolean
          lovable_background?: boolean
          lovable_chat?: boolean
          use_gemini?: boolean
          user_id: string
        }
        Update: {
          chat_provider?: string
          use_nvidia_chat?: boolean
          embedding_issue?: string | null
          background_text_issue?: string | null
          use_nvidia?: boolean
          use_openrouter?: boolean
          lovable_background?: boolean
          lovable_chat?: boolean
          use_gemini?: boolean
          user_id?: string
        }
        Relationships: []
      }
      furina_chat_usage: {
        Row: {
          day: string
          provider: string
          requests: number
          tokens: number
          user_id: string
        }
        Insert: {
          day: string
          provider: string
          requests?: number
          tokens?: number
          user_id: string
        }
        Update: {
          day?: string
          provider?: string
          requests?: number
          tokens?: number
          user_id?: string
        }
        Relationships: []
      }
      furina_nvidia_chat_keys: {
        Row: {
          enabled: boolean
          created_at: string
          encrypted_value: string
          fingerprint: string
          id: string
          invalid: boolean
          suffix: string
          user_id: string
        }
        Insert: {
          enabled?: boolean
          created_at?: string
          encrypted_value: string
          fingerprint: string
          id?: string
          invalid?: boolean
          suffix: string
          user_id: string
        }
        Update: {
          enabled?: boolean
          created_at?: string
          encrypted_value?: string
          fingerprint?: string
          id?: string
          invalid?: boolean
          suffix?: string
          user_id?: string
        }
        Relationships: []
      }
      furina_nvidia_chat_state: {
        Row: { user_id: string; active_model: string | null; active_key_id: string | null; cooldowns: Json; last_notice: string | null; updated_at: string }
        Insert: { user_id: string; active_model?: string | null; active_key_id?: string | null; cooldowns?: Json; last_notice?: string | null; updated_at?: string }
        Update: { user_id?: string; active_model?: string | null; active_key_id?: string | null; cooldowns?: Json; last_notice?: string | null; updated_at?: string }
        Relationships: []
      }
      furina_gemini_keys: {
        Row: {
          created_at: string
          encrypted_value: string
          fingerprint: string
          id: string
          invalid: boolean
          suffix: string
          user_id: string
        }
        Insert: {
          created_at?: string
          encrypted_value: string
          fingerprint: string
          id?: string
          invalid?: boolean
          suffix: string
          user_id: string
        }
        Update: {
          created_at?: string
          encrypted_value?: string
          fingerprint?: string
          id?: string
          invalid?: boolean
          suffix?: string
          user_id?: string
        }
        Relationships: []
      }
      furina_openrouter_keys: {
        Row: {
          created_at: string
          encrypted_value: string
          fingerprint: string
          id: string
          invalid: boolean
          suffix: string
          user_id: string
        }
        Insert: {
          created_at?: string
          encrypted_value: string
          fingerprint: string
          id?: string
          invalid?: boolean
          suffix: string
          user_id: string
        }
        Update: {
          created_at?: string
          encrypted_value?: string
          fingerprint?: string
          id?: string
          invalid?: boolean
          suffix?: string
          user_id?: string
        }
        Relationships: []
      }
      furina_nvidia_keys: {
        Row: {
          created_at: string
          encrypted_value: string
          fingerprint: string
          id: string
          invalid: boolean
          suffix: string
          user_id: string
        }
        Insert: {
          created_at?: string
          encrypted_value: string
          fingerprint: string
          id?: string
          invalid?: boolean
          suffix: string
          user_id: string
        }
        Update: {
          created_at?: string
          encrypted_value?: string
          fingerprint?: string
          id?: string
          invalid?: boolean
          suffix?: string
          user_id?: string
        }
        Relationships: []
      }
      furina_identity_core: {
        Row: {
          revision: number
          state: Json
          user_id: string
        }
        Insert: {
          revision?: number
          state?: Json
          user_id: string
        }
        Update: {
          revision?: number
          state?: Json
          user_id?: string
        }
        Relationships: []
      }
      furina_memory_settings: {
        Row: {
          history_after: string | null
          use_history: boolean
          use_saved: boolean
          user_id: string
        }
        Insert: {
          history_after?: string | null
          use_history?: boolean
          use_saved?: boolean
          user_id: string
        }
        Update: {
          history_after?: string | null
          use_history?: boolean
          use_saved?: boolean
          user_id?: string
        }
        Relationships: []
      }
      furina_user_profile: {
        Row: {
          birth_date: string | null
          greeted_year: number | null
          user_id: string
        }
        Insert: {
          birth_date?: string | null
          greeted_year?: number | null
          user_id: string
        }
        Update: {
          birth_date?: string | null
          greeted_year?: number | null
          user_id?: string
        }
        Relationships: []
      }
      memories: {
        Row: {
          access_count: number
          character_id: string
          compressed: boolean
          content: string
          created_at: string
          dedup_checked_at: string | null
          nvidia_embedding: string | null
          embedding: string | null
          emotion: string | null
          id: string
          importance: number
          kind: string
          last_accessed_at: string
          merged_into: string | null
          occurred_at: string | null
          saved: boolean
          source_memory_ids: string[] | null
          user_id: string
        }
        Insert: {
          access_count?: number
          character_id?: string
          compressed?: boolean
          content: string
          created_at?: string
          dedup_checked_at?: string | null
          nvidia_embedding?: string | null
          embedding?: string | null
          emotion?: string | null
          id?: string
          importance?: number
          kind?: string
          last_accessed_at?: string
          merged_into?: string | null
          occurred_at?: string | null
          saved?: boolean
          source_memory_ids?: string[] | null
          user_id: string
        }
        Update: {
          access_count?: number
          character_id?: string
          compressed?: boolean
          content?: string
          created_at?: string
          dedup_checked_at?: string | null
          nvidia_embedding?: string | null
          embedding?: string | null
          emotion?: string | null
          id?: string
          importance?: number
          kind?: string
          last_accessed_at?: string
          merged_into?: string | null
          occurred_at?: string | null
          saved?: boolean
          source_memory_ids?: string[] | null
          user_id?: string
        }
        Relationships: []
      }
      messages: {
        Row: {
          audio_emotion: string | null
          audio_url: string | null
          content: string
          conversation_id: string
          created_at: string
          id: string
          image_url: string | null
          reply_to: Json | null
          role: string
          status: string
          sticker_id: string | null
          user_id: string
        }
        Insert: {
          audio_emotion?: string | null
          audio_url?: string | null
          content: string
          conversation_id: string
          created_at?: string
          id?: string
          image_url?: string | null
          reply_to?: Json | null
          role: string
          status?: string
          sticker_id?: string | null
          user_id: string
        }
        Update: {
          audio_emotion?: string | null
          audio_url?: string | null
          content?: string
          conversation_id?: string
          created_at?: string
          id?: string
          image_url?: string | null
          reply_to?: Json | null
          role?: string
          status?: string
          sticker_id?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "messages_conversation_id_fkey"
            columns: ["conversation_id"]
            isOneToOne: false
            referencedRelation: "conversations"
            referencedColumns: ["id"]
          },
        ]
      }
      user_settings: {
        Row: {
          data: Json
          updated_at: string
          user_id: string
        }
        Insert: {
          data?: Json
          updated_at?: string
          user_id: string
        }
        Update: {
          data?: Json
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      save_furina_nvidia_chat_state: {
        Args: { owner_id: string; model_id: string | null; key_id: string | null; blocked_until: Json; notice: string | null }
        Returns: undefined
      }

      claim_furina_memory_scan: {
        Args: { owner_id: string }
        Returns: {
          content: string
          embedding: string
          id: string
          kind: string
          occurred_at: string
        }[]
      }
      commit_furina_compaction: {
        Args: {
          owner_id: string
          source_ids: string[]
          summary_embedding: string
          summary_text: string
        }
        Returns: boolean
      }
      correct_furina_memory: {
        Args: {
          memory_id: string
          new_content: string
          new_embedding: string | null
          owner_id: string
        }
        Returns: boolean
      }
      correct_furina_nvidia_memory: {
        Args: {
          memory_id: string
          new_content: string
          new_embedding: string
          owner_id: string
        }
        Returns: boolean
      }
      create_furina_message_branch: {
        Args: { branch_id: string; branch_title: string; prefix: Json }
        Returns: undefined
      }
      recall_furina_recent: {
        Args: { owner_id: string; search_terms: string[]; excluded_thread: string | null }
        Returns: { thread_id: string; title: string; last_at: string; turns: Json }[]
      }
      recall_furina_text: {
        Args: {
          owner_id: string
          search_terms: string[]
          include_saved: boolean
          include_history: boolean
          overview: boolean
          history_day: string | null
          timezone_name: string
          active_thread: string | null
          thread_window_since: string | null
        }
        Returns: {
          id: string
          source: "saved" | "learned" | "user" | "assistant"
          content: string
          occurred_at: string | null
        }[]
      }
      find_furina_memories: {
        Args: {
          owner_id: string
          query_vec: string
          row_count: number
          since_time: string
          use_history: boolean
          use_saved: boolean
        }
        Returns: {
          content: string
          id: string
          kind: string
          occurred_at: string
          saved: boolean
          similarity: number
        }[]
      }
      find_furina_nvidia_memories: {
        Args: {
          owner_id: string
          query_vec: string
          row_count: number
          since_time: string
          use_history: boolean
          use_saved: boolean
        }
        Returns: {
          content: string
          id: string
          kind: string
          occurred_at: string
          saved: boolean
          similarity: number
        }[]
      }
      forget_furina_memory: {
        Args: { memory_id: string; owner_id: string }
        Returns: boolean
      }
      match_memories:
        | {
            Args: {
              match_character_id: string
              match_count?: number
              match_user_id: string
              query_embedding: string
            }
            Returns: {
              content: string
              id: string
              similarity: number
            }[]
          }
        | {
            Args: {
              include_compressed?: boolean
              match_character_id: string
              match_count?: number
              match_user_id: string
              query_embedding: string
            }
            Returns: {
              content: string
              id: string
              importance: number
              kind: string
              occurred_at: string
              similarity: number
            }[]
          }
      merge_furina_memories: {
        Args: {
          canonical_id: string
          merged_content: string
          merged_embedding: string
          owner_id: string
          snapshots: Json
        }
        Returns: boolean
      }
      record_furina_chat_usage: {
        Args: { owner_id: string; total_tokens: number; usage_provider: string }
        Returns: undefined
      }
      save_furina_gemini_key: {
        Args: {
          key_fingerprint: string
          key_suffix: string
          owner_id: string
          secret_box: string
        }
        Returns: string
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
