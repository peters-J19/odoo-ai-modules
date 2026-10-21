import logging

from odoo import api, fields, models
from odoo.tools import SQL

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.field_vector.fields import Vector, VectorValue

_logger = logging.getLogger(__name__)

SRS_EMBEDDING_MODEL = "text-embedding-3-small"
SRS_EMBEDDING_DIMENSIONS = 1536
SRS_EMBEDDING_BATCH_SIZE = 20

SRS_IVFFLAT_LISTS = 10
SRS_IVFFLAT_PROBES = 4

SRS_MIN_SIMILARITY = 0.42
SRS_EMBEDDABLE_TEXT_LIMIT = 24000


class SemanticSearchMixin(models.AbstractModel):
    _name = "semantic.search.mixin"
    _description = "Adds a tuned semantic-similarity search to a model"

    # --- Embedding storage -------------------------------------------------
    srs_embedding = Vector(dimensions=SRS_EMBEDDING_DIMENSIONS, string="Semantic Embedding")
    srs_embedding_text = fields.Text(string="Last Embedded Text", copy=False)
    srs_embedding_state = fields.Selection(
        # Intentionally no default because it would back-fill into every existing row the moment the field is added to a model
        selection=[
            ("to_process", "To Process"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        string="Embedding Status",
        copy=False,
    )

    def _get_embeddable_text(self):
        """Return the text that will be used to create the embedding for this record. 
        Must be overriden by any model that uses Semantic Record Search."""
        raise NotImplementedError(
            f"{self._name} must implement _get_embeddable_text() to use "
            "semantic.search.mixin."
        )

    def init(self):
        super().init()
        if self._abstract:
            # init_models() also calls init() on the raw mixin itself, not
            # just on concrete models that inherit it... the mixin has no
            # table of its own so there is nothing to index here. Concrete 
            # inheritors are not abstract and fall through normally.
            return
        # Same idiom as core Odoo's own hand-built indexes - a raw CREATE INDEX via
        # odoo.tools.SQL, run on every install/upgrade. Because this lives on
        # the mixin and reads self._table dynamically, every concrete model
        # that adopts the mixin gets its own index on its own table
        # automatically - no per-model index code needed.
        self.env.cr.execute(SQL(
            "CREATE INDEX IF NOT EXISTS %s ON %s "
            "USING ivfflat (srs_embedding vector_cosine_ops) WITH (lists = %s)",
            SQL.identifier(f"{self._table}_srs_embedding_idx"),
            SQL.identifier(self._table),
            SRS_IVFFLAT_LISTS,
        ))

    # --- Embedding lifecycle -------------------------------------------------

    def _update_embeddings(self):
        """Embed every record in ``self`` in ONE batched API call - matches
        the real precedent in Odoo's own ai/models/ai_embedding.py (its RAG
        chunk pipeline embeds in batches, not one call per chunk). Unlike
        Tier 1's per-ticket classification calls in Helpdesk AI Sorting, a
        batch's embedding call succeeds or fails as a whole (it's the same
        simple operation for every item, not independent per-record
        reasoning) - so error handling here is batch-level, not per-record
        savepoints."""
        if not self:
            return
        texts = []
        for record in self:
            text = record._get_embeddable_text()
            if len(text) > SRS_EMBEDDABLE_TEXT_LIMIT:
                text = text[:SRS_EMBEDDABLE_TEXT_LIMIT] + "..."
            texts.append(text)
        try:
            response = LLMApiService(self.env, "openai").get_embedding(
                input=texts,
                dimensions=SRS_EMBEDDING_DIMENSIONS,
                model=SRS_EMBEDDING_MODEL,
            )
            for record, text, item in zip(self, texts, response["data"]):
                super(SemanticSearchMixin, record).write({
                    "srs_embedding": item["embedding"],
                    "srs_embedding_text": text,
                    "srs_embedding_state": "done",
                })
        except Exception:
            _logger.exception(
                "Semantic embedding batch failed for %s%s", self._name, self.ids
            )
            super(SemanticSearchMixin, self).write({"srs_embedding_state": "error"})

    def write(self, vals):
        old_texts = {record.id: record._get_embeddable_text() for record in self}
        res = super().write(vals)
        changed = self.filtered(
            lambda r: r._get_embeddable_text() != old_texts.get(r.id)
        )
        if changed:
            super(SemanticSearchMixin, changed).write({"srs_embedding_state": "to_process"})
            changed._trigger_embedding_cron()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("srs_embedding_state", "to_process")
        records = super().create(vals_list)
        records._trigger_embedding_cron()
        return records

    def _trigger_embedding_cron(self):
        """Nudge whatever cron(s) target this model to run sooner, rather
        than waiting for the next scheduled interval. Deliberately generic -
        looked up by model, not by a hardcoded xmlid, so the mixin never
        needs to know which concrete model (and thus which cron) is calling
        it. Minor, accepted trade-off: if a model ever had some other,
        unrelated cron also targeting it (verified live: helpdesk.ticket
        already does - Helpdesk AI Sorting's own Tier 1 triage cron), this
        would nudge that one too - harmless, since crons no-op if their own
        search domain finds nothing to do. ir.cron's own _trigger() requires
        a single record (ensure_one()), so each match is triggered
        individually rather than as one recordset call."""
        for cron in self.env["ir.cron"].sudo().search(
            [("model_id.model", "=", self._name)]
        ):
            cron._trigger()

    def action_retry_embedding(self):
        """Manually retry embedding for a record stuck in 'error' - the cron
        deliberately never auto-retries an error-state record (a record that
        failed once, e.g. on a real API outage, would otherwise fail forever
        with no way back in except an unrelated text edit happening to touch
        it). Synchronous, same immediate-retry shape as Tier 1's own
        action_run_ai_triage in helpdesk_ai_sorting - the point of a manual
        retry button is seeing the result now, not queuing for the next cron
        pass."""
        self._update_embeddings()

    @api.model
    def _cron_update_embeddings(self, batch_size=SRS_EMBEDDING_BATCH_SIZE):
        records = self.search(
            [("srs_embedding_state", "not in", ["done", "error"])], limit=batch_size
        )
        if not records:
            return
        records._update_embeddings()
        if len(records) == batch_size:
            records._trigger_embedding_cron()

    # --- Search ---------------------------------------------------------

    @api.model
    def _find_similar(self, query_text, limit=10, min_similarity=SRS_MIN_SIMILARITY, exclude_ids=None):
        response = LLMApiService(self.env, "openai").get_embedding(
            input=query_text,
            dimensions=SRS_EMBEDDING_DIMENSIONS,
            model=SRS_EMBEDDING_MODEL,
        )
        vector = response["data"][0]["embedding"]
        return self._find_similar_by_vector(
            vector, limit=limit, min_similarity=min_similarity, exclude_ids=exclude_ids
        )

    def _find_similar_by_vector(self, vector, limit=10, min_similarity=SRS_MIN_SIMILARITY, exclude_ids=None):
        """Low-level cosine search. Split out from ``_find_similar`` so a
        future caller that already has a vector on hand (e.g. Phase 3: "find
        tickets similar to THIS ticket", which already has its own stored
        embedding) can reuse this without paying for a redundant embedding
        call."""
        limit = max(1, int(limit))
        self.env.cr.execute(SQL("SET LOCAL ivfflat.probes = %s", SRS_IVFFLAT_PROBES))
        self.env.cr.execute(SQL(
            "SELECT id FROM %s "
            "WHERE srs_embedding IS NOT NULL AND id != ALL(%s::int[]) "
            "AND (1 - (srs_embedding <=> %s::vector)) >= %s "
            "ORDER BY srs_embedding <=> %s::vector LIMIT %s",
            SQL.identifier(self._table),
            list(exclude_ids or []),
            VectorValue(vector),
            min_similarity,
            VectorValue(vector),
            limit,
        ))
        candidate_ids = [row[0] for row in self.env.cr.fetchall()]

        visible_ids = set(self.search([("id", "in", candidate_ids)]).ids)
        return self.browse([i for i in candidate_ids if i in visible_ids])
