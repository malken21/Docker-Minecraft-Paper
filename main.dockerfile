ARG JAVA_VERSION=21
FROM gcr.io/distroless/java${JAVA_VERSION}-debian13

COPY paper.jar app.jar

WORKDIR /app

CMD ["../app.jar"]
