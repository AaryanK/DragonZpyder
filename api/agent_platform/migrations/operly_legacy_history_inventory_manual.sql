-- Aggregate-only; no private IDs, message contents, or external subjects returned.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='45s';
WITH legacy AS (
 SELECT c.id,c.external_conversation_id,c.provider,p.user_id,
  EXISTS(SELECT 1 FROM public.agent_conversations a
   WHERE a.id IN(c.id,c.external_conversation_id)) AS workspace_agent_ref,
  EXISTS(SELECT 1 FROM public.agent_chat_conversations a
   WHERE a.scope_kind='workspace' AND a.id IN(c.id,c.external_conversation_id)) AS workspace_chat_ref,
  EXISTS(SELECT 1 FROM public.channel_conversation_states s
   WHERE s.active_tenant_id IS NOT NULL AND
    (s.external_conversation_id=c.external_conversation_id OR s.agent_conversation_id IN(c.id,c.external_conversation_id))) AS workspace_channel_ref,
  EXISTS(SELECT 1 FROM public.conversation_artifacts a
   WHERE a.tenant_id IS NOT NULL AND a.conversation_id IN(c.id,c.external_conversation_id)) AS workspace_artifact_ref
 FROM public.principal_conversations c JOIN public.principals p ON p.id=c.principal_id
 WHERE p.kind IN('human','user') AND p.status='active' AND p.user_id IS NOT NULL
)
SELECT provider,count(*) AS conversations,
 count(*) FILTER(WHERE workspace_agent_ref OR workspace_chat_ref OR workspace_channel_ref OR workspace_artifact_ref) AS workspace_references,
 count(*) FILTER(WHERE NOT EXISTS(SELECT 1 FROM public.app_users u WHERE u.id=legacy.user_id)) AS unknown_owners
FROM legacy GROUP BY provider ORDER BY provider;
SELECT c.provider,m.role,count(*) AS messages
FROM public.principal_messages m JOIN public.principal_conversations c ON c.id=m.conversation_id
GROUP BY c.provider,m.role ORDER BY c.provider,m.role;
-- Compare content within the same owner and role, never reveal the content.
-- This is candidate overlap only, not a safe deduplication decision.
SELECT c.provider,count(*) AS legacy_messages_matching_newer_content
FROM public.principal_messages m JOIN public.principal_conversations c ON c.id=m.conversation_id
JOIN public.principals p ON p.id=c.principal_id
WHERE EXISTS(SELECT 1 FROM public.agent_chat_messages n
 JOIN public.agent_chat_conversations nc ON nc.id=n.conversation_id
 WHERE nc.scope_kind='personal' AND nc.owner_user_id=p.user_id
 AND n.role=m.role AND n.content=m.content)
GROUP BY c.provider ORDER BY c.provider;
-- Classify conservatively. Absence of references is not positive proof of
-- personal scope; the legacy writer/authorization path must also be reviewed.
WITH scope AS (
 SELECT c.id,c.provider,p.user_id,
  CASE WHEN p.user_id IS NULL OR u.id IS NULL OR p.status<>'active'
          OR p.kind NOT IN('human','user') THEN 'owner_unverified'
       WHEN EXISTS(SELECT 1 FROM public.agent_conversations a
                    WHERE a.id IN(c.id,c.external_conversation_id))
         OR EXISTS(SELECT 1 FROM public.agent_chat_conversations a
                    WHERE a.scope_kind='workspace' AND a.id IN(c.id,c.external_conversation_id))
         OR EXISTS(SELECT 1 FROM public.channel_conversation_states s
                    WHERE s.active_tenant_id IS NOT NULL AND
                     (s.external_conversation_id=c.external_conversation_id OR s.agent_conversation_id IN(c.id,c.external_conversation_id)))
         OR EXISTS(SELECT 1 FROM public.conversation_artifacts a
                    WHERE a.tenant_id IS NOT NULL AND a.conversation_id IN(c.id,c.external_conversation_id))
          THEN 'workspace_reference'
       WHEN c.provider<>'operly_web' THEN 'channel_review'
       ELSE 'candidate_only' END AS classification
 FROM public.principal_conversations c JOIN public.principals p ON p.id=c.principal_id
 LEFT JOIN public.app_users u ON u.id=p.user_id
)
SELECT provider,classification,count(DISTINCT s.id) AS conversations,count(m.id) AS messages
FROM scope s LEFT JOIN public.principal_messages m ON m.conversation_id=s.id
GROUP BY provider,classification ORDER BY provider,classification;

-- Matching content by itself (e.g. repeated greetings) is not duplication.
-- Report matching timestamp and content separately, without exporting either.
SELECT count(*) FILTER(WHERE EXISTS(
 SELECT 1 FROM public.agent_chat_messages n
 JOIN public.agent_chat_conversations nc ON nc.id=n.conversation_id
 WHERE nc.scope_kind='personal' AND nc.owner_user_id=p.user_id
   AND n.role=m.role AND n.content=m.content AND n.created_at=m.created_at
)) AS exact_time_content_candidates
FROM public.principal_messages m JOIN public.principal_conversations c ON c.id=m.conversation_id
JOIN public.principals p ON p.id=c.principal_id;
ROLLBACK;
