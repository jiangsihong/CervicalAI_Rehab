# -*- coding: utf-8 -*-
"""Model architecture for the bundled RealHePoNet pose-estimator weights."""

from tensorflow.keras.layers import Conv2D, Dense, Dropout, Flatten, MaxPooling2D
from tensorflow.keras.models import Sequential


def mpatacchiola_generic(
    in_size,
    num_conv_blocks,
    num_filters_start,
    num_dense_layers,
    dense_layer_size,
    dropout_rate=0,
    batch_size=None,
):
    """Build the CNN architecture expected by pose-estimator.h5."""
    model = Sequential()

    model.add(
        Conv2D(
            num_filters_start,
            kernel_size=(3, 3),
            padding="same",
            activation="relu",
            input_shape=(in_size, in_size, 1),
            batch_size=batch_size,
        )
    )
    model.add(MaxPooling2D(pool_size=(2, 2)))

    for i in range(num_conv_blocks - 1):
        model.add(
            Conv2D(
                num_filters_start * (2 ** (i + 1)),
                kernel_size=(3, 3),
                padding="same",
                activation="relu",
            )
        )
        model.add(MaxPooling2D(pool_size=(2, 2)))

    model.add(Flatten())

    for _ in range(num_dense_layers):
        model.add(Dense(dense_layer_size))
        if dropout_rate != 0:
            model.add(Dropout(dropout_rate))

    model.add(Dense(2))
    return model
