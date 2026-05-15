import json
import sys
import argparse
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import tensorflow as tf

from ml.common import PreparedDatasetInfo, write_json
from ml import prepare_dataset
from ml import train


class FakeTokenizer:
    def __init__(self, offset: int = 0) -> None:
        self.offset = offset

    def tokenize(self, texts):
        words = tf.strings.split(texts)
        lengths = tf.cast(words.row_lengths(), tf.int64)
        return tf.ragged.range(
            tf.fill(tf.shape(lengths), tf.cast(self.offset + 1, tf.int64)),
            tf.cast(self.offset + 1, tf.int64) + lengths + 1,
        )


def prepared_info() -> PreparedDatasetInfo:
    return PreparedDatasetInfo(
        dataset_name="fake/enpt",
        max_tokens=8,
        train_records=3,
        val_records=2,
        tokenizer_dir="tokenizers/fake",
        pt_vocab_size=101,
        en_vocab_size=202,
    )


def train_args(**overrides) -> argparse.Namespace:
    defaults = {
        "epochs": 2,
        "batch_size": 4,
        "threshold": 0.30,
        "max_tokens": 8,
        "num_layers": 2,
        "d_model": 32,
        "num_heads": 4,
        "dff": 64,
        "dropout": 0.1,
        "warmup_steps": 100,
        "git_sha": "abc123",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_prepare_dataset_serializes_and_parses_example_roundtrip():
    serialized = prepare_dataset._serialize_example(
        tf.constant([1, 2, 3], dtype=tf.int64),
        tf.constant([4, 5, 6], dtype=tf.int64),
    )

    pt, en = prepare_dataset._parse_example(tf.constant(serialized))

    assert pt.numpy().tolist() == [1, 2, 3]
    assert en.numpy().tolist() == [4, 5, 6]


def test_prepare_dataset_int64_feature_materializes_values():
    feature = prepare_dataset._int64_feature([1, 2, 3])

    assert list(feature.int64_list.value) == [1, 2, 3]


def test_prepare_dataset_write_tfrecord_filters_short_examples(tmp_path: Path):
    class Tokenizers:
        pt = FakeTokenizer(offset=10)
        en = FakeTokenizer(offset=20)

    ds_text = tf.data.Dataset.from_tensor_slices(
        (
            tf.constant(["ola mundo", ""], dtype=tf.string),
            tf.constant(["hello world", ""], dtype=tf.string),
        )
    )

    output_path = tmp_path / "train.tfrecord"
    count = prepare_dataset.write_tfrecord(ds_text, Tokenizers(), output_path, max_tokens=5, max_records=1)

    records = list(tf.data.TFRecordDataset([str(output_path)]))
    pt, en = prepare_dataset._parse_example(records[0])
    assert count == 1
    assert len(records) == 1
    assert pt.numpy().tolist() == [11, 12, 13]
    assert en.numpy().tolist() == [21, 22, 23]


def test_prepare_dataset_orchestrates_tfds_and_writes_metadata(tmp_path: Path, monkeypatch):
    fake_examples = {
        "train": tf.data.Dataset.from_tensor_slices(
            (
                tf.constant(["ola", "bom dia"], dtype=tf.string),
                tf.constant(["hello", "good morning"], dtype=tf.string),
            )
        )
    }
    fake_tokenizers = SimpleNamespace(pt=object(), en=object())
    write_calls: list[tuple[Path, int | None]] = []

    def fake_write_tfrecord(ds_text, tokenizers, output_path, max_tokens, max_records):
        write_calls.append((output_path, max_records))
        return max_records or 0

    monkeypatch.setattr(prepare_dataset, "download_and_load_tokenizers", lambda tokenizers_dir: fake_tokenizers)
    monkeypatch.setattr(prepare_dataset.tfds, "load", lambda *args, **kwargs: (fake_examples, object()))
    monkeypatch.setattr(prepare_dataset, "write_tfrecord", fake_write_tfrecord)
    monkeypatch.setattr(prepare_dataset, "vocab_size", lambda tokenizer: 123 if tokenizer is fake_tokenizers.pt else 456)

    info = prepare_dataset.prepare_dataset(
        output_dir=tmp_path,
        max_tokens=16,
        train_records=7,
        val_records=3,
        seed=42,
        dataset_name="fake/enpt",
    )

    assert info.train_records == 7
    assert info.val_records == 3
    assert info.pt_vocab_size == 123
    assert info.en_vocab_size == 456
    assert write_calls == [(tmp_path / "train.tfrecord", 7), (tmp_path / "val.tfrecord", 3)]
    assert json.loads((tmp_path / "prepared_dataset.json").read_text(encoding="utf-8")) == asdict(info)


def test_prepare_dataset_main_prints_summary(tmp_path: Path, monkeypatch, capsys):
    info = prepared_info()

    def fake_prepare_dataset(**kwargs):
        assert kwargs["output_dir"] == tmp_path
        assert kwargs["dataset_name"] == "fake/enpt"
        assert kwargs["max_tokens"] == 12
        return info

    monkeypatch.setattr(prepare_dataset, "prepare_dataset", fake_prepare_dataset)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_dataset",
            "--output_dir",
            str(tmp_path),
            "--dataset_name",
            "fake/enpt",
            "--max_tokens",
            "12",
            "--train_records",
            "3",
            "--val_records",
            "2",
        ],
    )

    prepare_dataset.main()

    assert json.loads(capsys.readouterr().out) == {
        "stage": "prepare_dataset",
        "output_dir": tmp_path.as_posix(),
        "train_records": 3,
        "val_records": 2,
    }


def test_train_masked_metrics_ignore_padding_tokens():
    y_true = tf.constant([[1, 0], [2, 0]], dtype=tf.int64)
    y_pred = tf.constant(
        [
            [[0.1, 4.0, 0.1], [9.0, 0.1, 0.1]],
            [[0.1, 0.1, 4.0], [9.0, 0.1, 0.1]],
        ],
        dtype=tf.float32,
    )

    assert train.masked_accuracy(y_true, y_pred).numpy() == 1.0
    assert train.masked_loss(y_true, y_pred).numpy() > 0


def test_train_parse_example_roundtrip():
    serialized = prepare_dataset._serialize_example(
        tf.constant([3, 4], dtype=tf.int64),
        tf.constant([5, 6, 7], dtype=tf.int64),
    )

    pt, en = train._parse_example(tf.constant(serialized))

    assert pt.numpy().tolist() == [3, 4]
    assert en.numpy().tolist() == [5, 6, 7]


def test_train_translator_generates_text_until_end_token():
    class FakeTokenized:
        def __getitem__(self, item):
            return self

        def to_tensor(self):
            return tf.constant([[9, 8]], dtype=tf.int64)

    class FakePortugueseTokenizer:
        def tokenize(self, sentence):
            return FakeTokenized()

    class FakeEnglishTokenizer:
        def tokenize(self, text):
            return tf.constant([[1, 2]], dtype=tf.int64)

        def detokenize(self, tokens):
            return tf.constant(["translated"], dtype=tf.string)

    class FakeTransformer:
        def __call__(self, inputs, training=False):
            out_tokens = inputs[1]
            batch = tf.shape(out_tokens)[0]
            seq_len = tf.shape(out_tokens)[1]
            logits = tf.zeros((batch, seq_len, 3), dtype=tf.float32)
            end_token_logits = tf.ones((batch, seq_len, 1), dtype=tf.float32) * 10.0
            return tf.concat([logits[:, :, :2], end_token_logits], axis=-1)

    tokenizers = SimpleNamespace(pt=FakePortugueseTokenizer(), en=FakeEnglishTokenizer())
    translator = train.Translator(tokenizers, FakeTransformer(), max_tokens=4)
    export = train.ExportTranslator(translator)

    assert translator(tf.constant("ola")).numpy() == b"translated"
    assert export(tf.constant("ola")).numpy() == b"translated"


def test_train_loads_prepared_info_and_builds_model_config(tmp_path: Path):
    info = prepared_info()
    write_json(tmp_path / "prepared_dataset.json", asdict(info))

    loaded = train.load_prepared_info(tmp_path)
    cfg = train.build_model_config(train_args(), loaded)

    assert loaded == info
    assert cfg.pt_vocab_size == 101
    assert cfg.en_vocab_size == 202
    assert cfg.max_tokens == 8
    assert cfg.d_model == 32


def test_train_writes_run_artifacts_and_summary(tmp_path: Path, capsys):
    run_dir = tmp_path / "artifacts" / "nmt_test"
    export_dir = run_dir / "saved_model"
    export_dir.mkdir(parents=True)
    (export_dir / "saved_model.pb").write_bytes(b"fake model")
    info = prepared_info()
    args = train_args()
    cfg = train.build_model_config(args, info)

    artifact_info = train.write_run_artifacts(
        run_dir=run_dir,
        run_id="nmt_test",
        status="approved",
        metric_value=0.91,
        val_loss=0.12,
        args=args,
        prepared=info,
        cfg=cfg,
        export_dir=export_dir,
    )

    train.emit_summary(
        run_id="nmt_test",
        status="approved",
        metric_value=0.91,
        threshold=args.threshold,
        metadata_path=artifact_info["metadata_path"],
        export_dir=export_dir,
    )

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "approved"
    assert metadata["metric_value"] == 0.91
    assert metadata["prepared_dataset"] == asdict(info)
    assert json.loads((run_dir / "metrics.json").read_text(encoding="utf-8")) == {
        "val_loss": 0.12,
        "val_token_accuracy": 0.91,
    }
    assert json.loads(capsys.readouterr().out)["run_id"] == "nmt_test"


def test_train_build_training_dataset_reads_tfrecord(tmp_path: Path):
    record_path = tmp_path / "train.tfrecord"
    serialized = prepare_dataset._serialize_example(
        tf.constant([7, 8, 9, 10], dtype=tf.int64),
        tf.constant([1, 2, 3, 4], dtype=tf.int64),
    )
    with tf.io.TFRecordWriter(str(record_path)) as writer:
        writer.write(serialized)

    ds = train.build_training_dataset(record_path, batch_size=1, max_tokens=3, shuffle=False, seed=42)
    (pt, en_in), en_out = next(iter(ds))

    assert pt.numpy().tolist() == [[7, 8, 9]]
    assert en_in.numpy().tolist() == [[1, 2, 3]]
    assert en_out.numpy().tolist() == [[2, 3, 4]]


def test_train_main_orchestrates_training_and_writes_artifacts(tmp_path: Path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    artifacts_dir = tmp_path / "artifacts"
    data_dir.mkdir()
    write_json(data_dir / "prepared_dataset.json", asdict(prepared_info()))

    class FakeDataset:
        def __init__(self) -> None:
            self.repeat_calls = 0

        def repeat(self):
            self.repeat_calls += 1
            return self

    class FakeTransformer:
        instances: list["FakeTransformer"] = []

        def __init__(self, cfg) -> None:
            self.cfg = cfg
            self.compile_kwargs = {}
            self.fit_kwargs = {}
            FakeTransformer.instances.append(self)

        def compile(self, **kwargs) -> None:
            self.compile_kwargs = kwargs

        def fit(self, *args, **kwargs) -> None:
            self.fit_kwargs = kwargs

        def evaluate(self, *args, **kwargs) -> dict:
            return {"masked_accuracy": 0.75, "loss": 0.25}

    def fake_build_training_dataset(tfrecord_path, batch_size, max_tokens, shuffle, seed):
        return FakeDataset()

    def fake_save(export, export_dir: str) -> None:
        export_path = Path(export_dir)
        export_path.mkdir(parents=True)
        (export_path / "saved_model.pb").write_bytes(b"fake saved model")

    monkeypatch.setattr(train, "build_training_dataset", fake_build_training_dataset)
    monkeypatch.setattr(train, "Transformer", FakeTransformer)
    monkeypatch.setattr(train, "WarmupSchedule", lambda d_model, warmup_steps: "warmup")
    monkeypatch.setattr(train.tf.keras.optimizers, "Adam", lambda *args, **kwargs: "optimizer")
    monkeypatch.setattr(train.tf.keras.callbacks, "ModelCheckpoint", lambda **kwargs: ("checkpoint", kwargs))
    monkeypatch.setattr(train.tf.saved_model, "load", lambda path: SimpleNamespace(pt=object(), en=object()))
    monkeypatch.setattr(train.tf.saved_model, "save", fake_save)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train",
            "--data_dir",
            str(data_dir),
            "--artifacts_dir",
            str(artifacts_dir),
            "--run_id",
            "nmt_unit",
            "--git_sha",
            "unit-sha",
            "--threshold",
            "0.50",
            "--epochs",
            "1",
            "--batch_size",
            "2",
            "--max_tokens",
            "8",
        ],
    )

    train.main()

    run_dir = artifacts_dir / "nmt_unit"
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    summary = json.loads(capsys.readouterr().out)
    transformer = FakeTransformer.instances[0]

    assert metadata["status"] == "approved"
    assert metadata["metric_value"] == 0.75
    assert metadata["git_sha"] == "unit-sha"
    assert summary["run_id"] == "nmt_unit"
    assert summary["status"] == "approved"
    assert transformer.compile_kwargs["optimizer"] == "optimizer"
    assert transformer.fit_kwargs["epochs"] == 1
    assert transformer.fit_kwargs["steps_per_epoch"] == 2
    assert transformer.fit_kwargs["validation_steps"] == 1
