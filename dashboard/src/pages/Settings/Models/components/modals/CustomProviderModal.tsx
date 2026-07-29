/**
 * CustomProviderModal — create a new provider with a multi-model list.
 *
 * Mirrors finnie's CustomProviderModal shape:
 *   - Provider metadata form (name, kind, base_url, api_key)
 *   - Inline model list editor (add / remove models with input types)
 */
import { useEffect, useState } from "react";
import {
  Button,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  message,
} from "antd";
import { ChevronDown, ChevronUp, Plus, Trash2, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { request } from "../../../../../api/request";
import type { ProviderRow } from "../../useProviders";
import { ModelMetaTags } from "../../modelMeta";
import { enrichWizardModel } from "../../wizardModelMeta";
import { fetchProviderModels, testProviderDraft } from "../../providerApi";
import styles from "../../index.module.less";

interface CustomProviderModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  /** API path prefix for POST. Defaults to "/providers". */
  apiPrefix?: string;
}

interface InitialModel {
  id: string;
  name: string;
  input: string[];
  max_tokens?: number;
  context_window?: number;
  reasoning?: boolean;
}

const KINDS = [
  { value: "openai", labelKey: "kindOpenaiCompat" as const },
  { value: "anthropic", labelKey: "anthropic" as const },
  { value: "bedrock", labelKey: "bedrock" as const },
];

const INPUT_TYPE_OPTIONS = [
  { value: "text", label: "inputTypeText" as const },
  { value: "image", label: "inputTypeImage" as const },
  { value: "audio", label: "inputTypeAudio" as const },
];

export function CustomProviderModal({
  open,
  onClose,
  onSaved,
  apiPrefix = "/providers",
}: CustomProviderModalProps) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [form] = Form.useForm();
  const [models, setModels] = useState<InitialModel[]>([]);
  const [adding, setAdding] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [modelForm] = Form.useForm();

  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue({ kind: "openai" });
      modelForm.resetFields();
      setModels([]);
      setAdding(false);
      setShowAdvanced(false);
    }
  }, [open, form, modelForm]);

  const handleAddModel = async () => {
    try {
      const values = await modelForm.validateFields();
      const id = (values.id as string).trim();
      if (models.some((m) => m.id === id)) {
        message.warning(t("models.initialModelDuplicate", { name: id }));
        return;
      }
      const name = (values.name as string | undefined)?.trim() || id;
      const input: string[] = (values.input as string[] | undefined) || [
        "text",
      ];
      const contextWindow =
        values.context_window != null
          ? (values.context_window as number)
          : undefined;
      const maxTokens =
        values.max_tokens != null ? (values.max_tokens as number) : undefined;
      const reasoning =
        values.reasoning != null ? (values.reasoning as boolean) : undefined;
      const meta = enrichWizardModel(
        {
          id,
          name,
          input,
          context_window: contextWindow,
          max_tokens: maxTokens,
          reasoning,
        },
        t,
      );
      const entry: InitialModel = {
        id,
        name,
        input: meta.input,
      };
      if (maxTokens != null) entry.max_tokens = maxTokens;
      if (contextWindow != null) entry.context_window = contextWindow;
      if (meta.reasoning) entry.reasoning = true;
      setModels((prev) => [...prev, entry]);
      modelForm.resetFields();
      setAdding(false);
      setShowAdvanced(false);
    } catch {
      // validation error — ignore
    }
  };

  const handleRemoveModel = (modelId: string) => {
    setModels((prev) => prev.filter((m) => m.id !== modelId));
  };

  const handleTest = async () => {
    try {
      const values = await form.validateFields();
      const kind = values.kind as string;
      const apiKey = (values.api_key as string | undefined)?.trim();
      const baseUrl = (values.base_url as string | undefined)?.trim() || null;
      const name = (values.name as string).trim();

      if (!apiKey) {
        message.warning(t("models.pleaseEnterApiKey"));
        return;
      }

      // For OpenAI-compatible endpoints we can auto-discover models via /v1/models.
      // This avoids forcing the user to type model IDs manually.
      if (kind === "openai") {
        setFetchingModels(true);
        const fetchResult = await fetchProviderModels({
          name,
          kind,
          api_key: apiKey,
          base_url: baseUrl,
        });

        if (!fetchResult.ok) {
          message.error(
            t("models.fetchModelsFailed", {
              error: fetchResult.error ?? "unknown",
            }),
          );
          return;
        }

        const fetched = fetchResult.models ?? [];
        if (fetched.length === 0) {
          message.warning(t("models.fetchModelsEmpty"));
          return;
        }

        setModels((prev) => {
          const existingIds = new Set(prev.map((m) => m.id));
          const additions: InitialModel[] = [];
          for (const raw of fetched) {
            if (existingIds.has(raw.id)) continue;
            existingIds.add(raw.id);
            const meta = enrichWizardModel(
              {
                id: raw.id,
                name: raw.name !== raw.id ? raw.name : raw.id,
                input: ["text"],
              },
              t,
            );
            const entry: InitialModel = {
              id: raw.id,
              name: raw.name !== raw.id ? raw.name : raw.id,
              input: meta.input,
            };
            if (meta.reasoning) entry.reasoning = true;
            additions.push(entry);
          }
          return [...prev, ...additions];
        });

        message.success(
          t("models.fetchModelsSuccess", { count: fetched.length }),
        );
        return;
      }

      // Non-OpenAI providers still require a manual model entry to test against.
      if (models.length === 0) {
        message.warning(t("models.testDraftNeedModel"));
        return;
      }
      setTesting(true);
      const result = await testProviderDraft({
        name,
        kind,
        api_key: apiKey,
        base_url: baseUrl,
        model_id: models[0].id,
      });
      if (result.ok) {
        message.success(
          t("models.testSuccess", {
            name: models[0].name,
            time: result.latency_ms ?? 0,
          }),
        );
      } else {
        message.error(
          t("models.testConnectionFailed", {
            error: result.error ?? "unknown",
          }),
        );
      }
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(
        err instanceof Error ? err.message : t("models.testFailedSimple"),
      );
    } finally {
      setTesting(false);
      setFetchingModels(false);
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const modelEntries = models.map((m) => {
        const entry: Record<string, unknown> = {
          id: m.id,
          name: m.name,
          enabled: true,
          input: m.input.length > 0 ? m.input : ["text"],
          thinking: null,
        };
        if (m.max_tokens != null) entry.max_tokens = m.max_tokens;
        if (m.context_window != null) entry.context_window = m.context_window;
        if (m.reasoning) entry.reasoning = true;
        return entry;
      });

      await request<ProviderRow>(apiPrefix, {
        method: "POST",
        body: JSON.stringify({
          name: (values.name as string).trim(),
          kind: values.kind as string,
          base_url: (values.base_url as string | undefined)?.trim() || null,
          api_key: (values.api_key as string | undefined)?.trim() || null,
          models: modelEntries.length > 0 ? modelEntries : [],
          note: (values.note as string | undefined)?.trim() || null,
        }),
      });
      message.success(
        t("models.providerCreatedSimple", {
          name: (values.name as string).trim(),
        }),
      );
      await onSaved();
      onClose();
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error ? error.message : t("models.createFailedSimple");
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={t("models.addCustomProvider")}
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={saving}
      okText={t("common.create")}
      cancelText={t("common.cancel")}
      destroyOnHidden
      width={560}
      footer={
        <Space>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button
            icon={<Zap size={14} />}
            loading={testing || fetchingModels}
            onClick={() => void handleTest()}
          >
            {fetchingModels
              ? t("models.fetchingModels")
              : t("models.testConnection")}
          </Button>
          <Button
            type="primary"
            loading={saving}
            onClick={() => void handleSubmit()}
          >
            {t("common.create")}
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="name"
          label={t("models.nameLabel")}
          rules={[{ required: true, message: t("models.pleaseEnterName") }]}
        >
          <Input placeholder={t("models.namePlaceholder")} />
        </Form.Item>

        <Form.Item
          name="kind"
          label={t("models.kindLabel")}
          rules={[{ required: true, message: t("models.pleaseSelectKind") }]}
        >
          <Select
            options={KINDS.map((k) => ({
              value: k.value,
              label:
                k.value === "openai"
                  ? t("models.kindOpenaiCompat")
                  : k.value === "anthropic"
                  ? "Anthropic"
                  : "AWS Bedrock",
            }))}
          />
        </Form.Item>

        <Form.Item
          name="base_url"
          label="Base URL"
          extra={t("models.baseUrlExtra")}
        >
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>

        <Form.Item name="api_key" label="API Key">
          <Input.Password placeholder="sk-..." visibilityToggle />
        </Form.Item>

        <Form.Item name="note" label={t("models.noteLabel")}>
          <Input.TextArea rows={2} placeholder={t("models.notePlaceholder")} />
        </Form.Item>
      </Form>

      {/* ── Model list ── */}
      <Divider style={{ margin: "8px 0 12px" }}>
        {t("models.initialModelsLabel")}
      </Divider>

      <div className={styles.initialModelsHintText} style={{ marginBottom: 8 }}>
        {t("models.initialModelsHint")}
      </div>

      <div className={styles.modelList}>
        {models.length === 0 ? (
          <div className={styles.modelListEmpty}>{t("models.noModels")}</div>
        ) : (
          models.map((m) => (
            <div key={m.id} className={styles.modelListItem}>
              <div className={styles.modelListItemInfo}>
                <span className={styles.modelListItemName}>{m.name}</span>
                {m.name !== m.id && (
                  <span className={styles.modelListItemId}>{m.id}</span>
                )}
                <ModelMetaTags
                  includeText
                  input={m.input}
                  context_window={m.context_window}
                  max_tokens={m.max_tokens}
                  reasoning={m.reasoning}
                />
              </div>
              <div className={styles.modelListItemActions}>
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<Trash2 size={14} />}
                  onClick={() => handleRemoveModel(m.id)}
                />
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── Add model form ── */}
      {adding ? (
        <div className={styles.modelAddForm}>
          <Form form={modelForm} layout="vertical" style={{ marginBottom: 0 }}>
            <Form.Item
              name="id"
              label={t("models.modelIdLabel")}
              rules={[{ required: true, message: t("models.modelIdLabel") }]}
              style={{ marginBottom: 12 }}
            >
              <Input placeholder={t("models.modelIdPlaceholder")} />
            </Form.Item>
            <Form.Item
              name="name"
              label={t("models.modelNameLabel")}
              style={{ marginBottom: 12 }}
            >
              <Input placeholder={t("models.modelNamePlaceholder")} />
            </Form.Item>
            <Form.Item
              name="input"
              label={t("models.inputTypes")}
              initialValue={["text"]}
              style={{ marginBottom: 12 }}
            >
              <Select
                mode="multiple"
                allowClear
                placeholder={t("models.inputTypes")}
                options={INPUT_TYPE_OPTIONS.map((opt) => ({
                  value: opt.value,
                  label: t(`models.${opt.label}`),
                }))}
              />
            </Form.Item>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: showAdvanced ? 8 : 12,
              }}
            >
              <Button
                type="link"
                size="small"
                style={{ padding: 0 }}
                icon={
                  showAdvanced ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )
                }
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced
                  ? t("models.hideAdvanced")
                  : t("models.showAdvanced")}
              </Button>
            </div>
            {showAdvanced && (
              <div
                style={{
                  background:
                    "var(--ant-color-fill-quaternary, rgba(0,0,0,0.02))",
                  borderRadius: 6,
                  padding: "12px 12px 4px",
                  marginBottom: 12,
                }}
              >
                <div style={{ display: "flex", gap: 12 }}>
                  <Form.Item
                    name="context_window"
                    label={t("models.contextWindow")}
                    style={{ flex: 1, marginBottom: 10 }}
                  >
                    <InputNumber
                      min={0}
                      style={{ width: "100%" }}
                      placeholder={t("models.contextWindowPlaceholder")}
                    />
                  </Form.Item>
                  <Form.Item
                    name="max_tokens"
                    label={t("models.maxTokens")}
                    style={{ flex: 1, marginBottom: 10 }}
                  >
                    <InputNumber
                      min={0}
                      style={{ width: "100%" }}
                      placeholder={t("models.maxTokensPlaceholder")}
                    />
                  </Form.Item>
                </div>
                <Form.Item
                  name="reasoning"
                  label={t("models.reasoning")}
                  valuePropName="checked"
                  style={{ marginBottom: 10 }}
                >
                  <Switch size="small" />
                </Form.Item>
              </div>
            )}
            <div
              style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}
            >
              <Button
                size="small"
                onClick={() => {
                  setAdding(false);
                  setShowAdvanced(false);
                  modelForm.resetFields();
                }}
              >
                {t("common.cancel")}
              </Button>
              <Button type="primary" size="small" onClick={handleAddModel}>
                {t("models.addModel")}
              </Button>
            </div>
          </Form>
        </div>
      ) : (
        <Button
          type="dashed"
          block
          icon={<Plus size={14} />}
          onClick={() => setAdding(true)}
          style={{ marginTop: 12 }}
        >
          {t("models.addModel")}
        </Button>
      )}
    </Modal>
  );
}
