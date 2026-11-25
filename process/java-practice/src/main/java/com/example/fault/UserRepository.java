package com.example.fault;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * 用户 Repository。继承即全套 CRUD，本步不加自定义查询。
 */
public interface UserRepository extends JpaRepository<UserEntity, Long> {
}
