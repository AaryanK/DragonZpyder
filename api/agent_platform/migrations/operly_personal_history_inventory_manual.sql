-- Read-only aggregate personal history preflight. Run only on Operly.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='30s';
SELECT count(*) AS conversations,
 count(DISTINCT c.owner_user_id) AS distinct_owners,
 count(*) FILTER (WHERE u.id IS NULL) AS unknown_owners,
 count(*) FILTER (WHERE c.workspace_id IS NOT NULL) AS workspace_conflicts,
 count(*) FILTER (WHERE c.authority_user_id IS NOT NULL AND c.authority_user_id<>c.owner_user_id) AS authority_conflicts,
 count(*) FILTER (WHERE c.id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS noncanonical_ids
FROM public.agent_chat_conversations c
LEFT JOIN public.app_users u ON u.id=c.owner_user_id
WHERE c.scope_kind='personal';
SELECT c.channel,c.surface,count(DISTINCT c.id) AS conversations,count(m.id) AS messages
FROM public.agent_chat_conversations c LEFT JOIN public.agent_chat_messages m ON m.conversation_id=c.id
WHERE c.scope_kind='personal' GROUP BY c.channel,c.surface ORDER BY c.channel,c.surface;
SELECT m.role,count(*) AS messages,
 coalesce(max(octet_length(m.content)),0) AS max_message_bytes,
 coalesce(sum(octet_length(m.content)),0) AS total_message_bytes
FROM public.agent_chat_messages m JOIN public.agent_chat_conversations c ON c.id=m.conversation_id
WHERE c.scope_kind='personal' GROUP BY m.role ORDER BY m.role;
SELECT p.kind,p.status,count(DISTINCT c.id) AS conversations,count(m.id) AS messages,
 count(DISTINCT c.id) FILTER(WHERE p.user_id IS NOT NULL) AS linked_conversations
FROM public.principal_conversations c JOIN public.principals p ON p.id=c.principal_id
LEFT JOIN public.principal_messages m ON m.conversation_id=c.id
GROUP BY p.kind,p.status ORDER BY p.kind,p.status;
SELECT column_name,data_type FROM information_schema.columns
WHERE table_schema='public' AND table_name='conversation_artifacts' ORDER BY ordinal_position;
ROLLBACK;
